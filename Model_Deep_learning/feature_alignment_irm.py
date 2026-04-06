"""
IRM + SupCon + C-MMD Extension for Feature Alignment

Mở rộng feature_alignment.py với:
1. IRMv1 Penalty — buộc model học invariant features across environments
2. MMD Loss — align latent distributions giữa UQ và CIC (global, backward compat)
3. Supervised Contrastive Loss — kéo Z cùng class lại gần, đẩy khác class ra xa (cross-domain)
4. Class-Conditional MMD — align per-class distributions thay vì global
5. PairedEnvironmentLoader — yield (x_uq, y_uq, x_cic, y_cic) đồng thời

Tất cả components gốc (FeatureAligner, extractors, TimeSeriesDataset, constants)
được import trực tiếp từ feature_alignment.py.
"""

import numpy as np
import torch
import torch.nn as nn
import torch.autograd as autograd
from torch.utils.data import DataLoader
from itertools import cycle

from feature_alignment import (
    FeatureAligner, UQFeatureExtractor, CICFeatureExtractor,
    TimeSeriesDataset, create_dataloaders,
    prepare_combined_dataset, prepare_dataset,
    DEVICE, LATENT_DIM, WINDOW_SIZE, NUM_CLASSES, UNIFIED_CLASSES,
)


# ============================================================
# IRMv1 PENALTY
# ============================================================

def compute_irm_penalty(logits, labels):
    """
    Compute IRMv1 penalty: ||∇_w [w · CE(logits, y)]||² at w=1.0

    Trực giác: Nếu model đã học optimal classifier cho environment này,
    thì nhân logits với scalar w=1 không nên thay đổi loss → gradient = 0.
    Nếu gradient ≠ 0 → classifier chưa optimal → model đang dựa vào
    features không invariant (spurious correlation).

    Args:
        logits: (batch, num_classes) — raw logits BEFORE softmax
        labels: (batch,) — integer class labels

    Returns:
        penalty: scalar — ||∇_w L(w·logits, y)||²
    """
    # Dummy scalar w = 1.0, requires grad for computing ∇_w
    w = torch.tensor(1.0, device=logits.device, requires_grad=True)

    # Scale logits by w
    loss = nn.functional.cross_entropy(logits * w, labels)

    # Compute gradient of loss w.r.t. w
    grad = autograd.grad(loss, w, create_graph=True)[0]

    # IRM penalty = ||grad||² = grad²
    return grad ** 2


# ============================================================
# MMD LOSS (Multi-scale Gaussian RBF Kernel)
# ============================================================

def gaussian_kernel(x, y, sigmas=None):
    """
    Compute multi-scale Gaussian RBF kernel matrix between x and y.

    Args:
        x: (n, d) tensor
        y: (m, d) tensor
        sigmas: list of bandwidth parameters

    Returns:
        kernel_val: (n, m) kernel matrix
    """
    if sigmas is None:
        sigmas = [0.1, 0.5, 1.0, 2.0, 5.0, 10.0]

    xx = (x * x).sum(dim=1, keepdim=True)  # (n, 1)
    yy = (y * y).sum(dim=1, keepdim=True)  # (m, 1)
    dist_sq = xx + yy.t() - 2.0 * x @ y.t()  # (n, m)
    dist_sq = torch.clamp(dist_sq, min=0.0)

    kernel_val = torch.zeros_like(dist_sq)
    for sigma in sigmas:
        gamma = 1.0 / (2.0 * sigma ** 2)
        kernel_val = kernel_val + torch.exp(-gamma * dist_sq)
    return kernel_val / len(sigmas)


def mmd_loss(source, target, sigmas=None):
    """
    Compute MMD² (Maximum Mean Discrepancy) between source and target.

    MMD² = E[k(s,s)] + E[k(t,t)] - 2·E[k(s,t)]

    Args:
        source: (n, d) — latent embeddings from environment 1
        target: (m, d) — latent embeddings from environment 2

    Returns:
        mmd_squared: scalar
    """
    n = source.size(0)
    m = target.size(0)

    k_ss = gaussian_kernel(source, source, sigmas)
    k_tt = gaussian_kernel(target, target, sigmas)
    k_st = gaussian_kernel(source, target, sigmas)

    mmd = (k_ss.sum() / (n * n)
           + k_tt.sum() / (m * m)
           - 2.0 * k_st.sum() / (n * m))
    return mmd


# ============================================================
# SUPERVISED CONTRASTIVE LOSS (Khosla et al. 2020)
# ============================================================

def supervised_contrastive_loss(z, labels, temperature=0.1):
    """
    Supervised Contrastive Loss — kéo Z cùng class lại gần, đẩy khác class ra xa.

    Hoạt động cross-domain: BruteForce từ UQ và BruteForce từ CIC
    được coi là cùng class → kéo lại gần nhau trong Z space.

    Args:
        z: (N, D) — latent embeddings, SHOULD be mean-pooled over time
        labels: (N,) — integer class labels
        temperature: τ scaling factor (smaller = sharper contrast)

    Returns:
        loss: scalar — average SupCon loss over all valid anchors
    """
    z = nn.functional.normalize(z, dim=1)  # L2-normalize

    # Cosine similarity matrix: (N, N)
    sim = z @ z.t() / temperature  # (N, N)

    N = z.size(0)

    # Mask: same class pairs (excluding self)
    labels_col = labels.unsqueeze(0)  # (1, N)
    labels_row = labels.unsqueeze(1)  # (N, 1)
    positive_mask = (labels_row == labels_col).float()  # (N, N)
    self_mask = torch.eye(N, device=z.device)
    positive_mask = positive_mask - self_mask  # exclude self

    # Number of positives per anchor
    num_positives = positive_mask.sum(dim=1)  # (N,)

    # Mask out anchors with no positives (class with only 1 sample)
    valid_anchor = (num_positives > 0)
    if valid_anchor.sum() == 0:
        return torch.tensor(0.0, device=z.device, requires_grad=True)

    # Log-sum-exp over all negatives + positives (excluding self)
    # For numerical stability, subtract max
    logits_max, _ = sim.max(dim=1, keepdim=True)
    logits = sim - logits_max.detach()  # (N, N)

    # Denominator: sum over all j ≠ i
    neg_mask = 1.0 - self_mask  # all except self
    exp_logits = torch.exp(logits) * neg_mask  # (N, N)
    log_denom = torch.log(exp_logits.sum(dim=1, keepdim=True) + 1e-8)  # (N, 1)

    # Log-prob of positives
    log_prob = logits - log_denom  # (N, N)

    # Average log-prob over positives for each anchor
    mean_log_prob = (positive_mask * log_prob).sum(dim=1) / (num_positives + 1e-8)  # (N,)

    # Loss = -mean over valid anchors
    loss = -(mean_log_prob[valid_anchor]).mean()
    return loss


# ============================================================
# CLASS-CONDITIONAL MMD
# ============================================================

def class_conditional_mmd(z_uq, y_uq, z_cic, y_cic,
                          num_classes=NUM_CLASSES, subsample=256):
    """
    Compute MMD riêng cho từng class rồi lấy trung bình.

    Thay vì align toàn bộ phân phối (global MMD bị Benign dominate),
    C-MMD ép buộc: BruteForce_UQ align với BruteForce_CIC,
    DoS_UQ align với DoS_CIC, v.v.

    Args:
        z_uq: (N_uq, D) — latent embeddings from UQ
        y_uq: (N_uq,) — class labels for UQ
        z_cic: (N_cic, D) — latent embeddings from CIC
        y_cic: (N_cic,) — class labels for CIC
        num_classes: number of classes
        subsample: max samples per class per domain for kernel computation

    Returns:
        cmmd: scalar — mean of per-class MMD losses
    """
    class_mmds = []

    for c in range(num_classes):
        mask_uq = (y_uq == c)
        mask_cic = (y_cic == c)

        z_uq_c = z_uq[mask_uq]
        z_cic_c = z_cic[mask_cic]

        # Skip classes with insufficient samples in either domain
        if z_uq_c.size(0) < 2 or z_cic_c.size(0) < 2:
            continue

        # Subsample for memory efficiency
        if z_uq_c.size(0) > subsample:
            idx = torch.randperm(z_uq_c.size(0))[:subsample]
            z_uq_c = z_uq_c[idx]
        if z_cic_c.size(0) > subsample:
            idx = torch.randperm(z_cic_c.size(0))[:subsample]
            z_cic_c = z_cic_c[idx]

        class_mmds.append(mmd_loss(z_uq_c, z_cic_c))

    if len(class_mmds) == 0:
        return torch.tensor(0.0, device=z_uq.device, requires_grad=True)

    return torch.stack(class_mmds).mean()


# ============================================================
# PAIRED ENVIRONMENT LOADER
# ============================================================

class PairedEnvironmentLoader:
    """
    Yield (x_uq, y_uq, x_cic, y_cic) tuples đồng thời.

    Handles different dataset sizes bằng cách cycle dataset nhỏ hơn.
    Mỗi epoch kết thúc khi dataset LỚN HƠN hết batches.

    Args:
        uq_windows, uq_labels: numpy arrays cho UQ data
        cic_windows, cic_labels: numpy arrays cho CIC data
        batch_size: batch size cho từng environment
        shuffle: whether to shuffle each epoch
    """

    def __init__(self, uq_windows, uq_labels, cic_windows, cic_labels,
                 batch_size=256, shuffle=True):
        self.uq_ds = TimeSeriesDataset(uq_windows, uq_labels, 'uq')
        self.cic_ds = TimeSeriesDataset(cic_windows, cic_labels, 'cic')
        self.batch_size = batch_size
        self.shuffle = shuffle

        # Determine which dataset is longer
        self.n_batches = max(
            len(self.uq_ds) // batch_size + 1,
            len(self.cic_ds) // batch_size + 1
        )

    def __iter__(self):
        uq_loader = DataLoader(
            self.uq_ds, batch_size=self.batch_size,
            shuffle=self.shuffle, num_workers=0, pin_memory=True,
            drop_last=True
        )
        cic_loader = DataLoader(
            self.cic_ds, batch_size=self.batch_size,
            shuffle=self.shuffle, num_workers=0, pin_memory=True,
            drop_last=True
        )

        # Cycle the shorter dataset
        if len(self.uq_ds) >= len(self.cic_ds):
            primary, secondary = iter(uq_loader), cycle(cic_loader)
            primary_is_uq = True
        else:
            primary, secondary = iter(cic_loader), cycle(uq_loader)
            primary_is_uq = False

        for p_batch in primary:
            s_batch = next(secondary)
            if primary_is_uq:
                x_uq, y_uq, _ = p_batch
                x_cic, y_cic, _ = s_batch
            else:
                x_cic, y_cic, _ = p_batch
                x_uq, y_uq, _ = s_batch

            yield x_uq, y_uq, x_cic, y_cic

    def __len__(self):
        return self.n_batches


# ============================================================
# IRM + MMD TRAINING FUNCTION
# ============================================================

def train_base_model_irm(model, uq_train_X, uq_train_y, cic_train_X, cic_train_y,
                         uq_val_X, uq_val_y, cic_val_X, cic_val_y,
                         epochs=30, lr=1e-3, batch_size=256,
                         lambda_irm_max=10.0, lambda_mmd=0.0,
                         lambda_supcon=0.1, lambda_cmmd=0.5,
                         supcon_temperature=0.1,
                         warmup_epochs=5, mmd_subsample=1024,
                         patience=5, verbose=True):
    """
    Train AlignerWithModel with IRM + SupCon + C-MMD.

    Loss = (CE_uq + CE_cic)/2
         + λ_irm × (IRM_uq + IRM_cic)/2
         + λ_supcon × SupCon(z_all, y_all)
         + λ_cmmd × C-MMD(z_uq, y_uq, z_cic, y_cic)
         [+ λ_mmd × global MMD — kept for backward compat, default 0]

    Args:
        model: AlignerWithModel instance
        uq_train_X, uq_train_y: UQ training data
        cic_train_X, cic_train_y: CIC training data
        uq_val_X, uq_val_y: UQ validation data
        cic_val_X, cic_val_y: CIC validation data
        epochs: max training epochs
        lr: learning rate
        batch_size: batch size per environment
        lambda_irm_max: max IRM penalty weight (after warmup)
        lambda_mmd: global MMD weight (default 0 — replaced by C-MMD)
        lambda_supcon: SupCon loss weight
        lambda_cmmd: Class-Conditional MMD weight
        supcon_temperature: SupCon temperature τ
        warmup_epochs: pure ERM epochs before IRM kicks in
        mmd_subsample: max samples for MMD kernel computation
        patience: early stopping patience
        verbose: print progress

    Returns:
        model: trained model (best checkpoint loaded)
        best_val_loss: best validation loss
        history: dict with per-epoch loss components
    """
    from copy import deepcopy

    model = model.to(DEVICE)

    # Class weights (combined from both environments)
    all_y = np.concatenate([uq_train_y, cic_train_y])
    cc = np.bincount(all_y, minlength=NUM_CLASSES).astype(float)
    cw = 1.0 / (cc + 1e-6)
    cw = cw / cw.sum() * NUM_CLASSES
    criterion = nn.CrossEntropyLoss(weight=torch.FloatTensor(cw).to(DEVICE))

    optimizer = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, 'min', patience=2, factor=0.5
    )

    # Paired loader for training
    train_loader = PairedEnvironmentLoader(
        uq_train_X, uq_train_y, cic_train_X, cic_train_y,
        batch_size=batch_size, shuffle=True
    )

    # Validation loaders
    uq_val_loader = create_dataloaders(uq_val_X, uq_val_y, 'uq', batch_size, False)
    cic_val_loader = create_dataloaders(cic_val_X, cic_val_y, 'cic', batch_size, False)

    best_val_loss = float('inf')
    best_state = None
    patience_ctr = 0

    history = {
        'ce': [], 'irm': [], 'mmd': [], 'supcon': [], 'cmmd': [],
        'total': [], 'val_loss': [], 'lambda_irm': []
    }

    for epoch in range(epochs):
        model.train()

        # --- IRM annealing ---
        if epoch < warmup_epochs:
            lambda_irm = 0.0  # Pure ERM during warmup
        else:
            # Linear ramp from 0 to lambda_irm_max
            progress = (epoch - warmup_epochs) / max(epochs - warmup_epochs, 1)
            lambda_irm = lambda_irm_max * min(progress, 1.0)

        epoch_ce, epoch_irm, epoch_mmd = 0.0, 0.0, 0.0
        epoch_supcon, epoch_cmmd = 0.0, 0.0
        n_steps = 0

        for x_uq, y_uq, x_cic, y_cic in train_loader:
            x_uq, y_uq = x_uq.to(DEVICE), y_uq.to(DEVICE)
            x_cic, y_cic = x_cic.to(DEVICE), y_cic.to(DEVICE)

            # --- Forward both environments ---
            logits_uq = model(x_uq, 'uq')
            logits_cic = model(x_cic, 'cic')

            # --- Classification loss (per environment, averaged) ---
            ce_uq = criterion(logits_uq, y_uq)
            ce_cic = criterion(logits_cic, y_cic)
            loss_ce = (ce_uq + ce_cic) / 2.0

            # --- IRM penalty (per environment, averaged) ---
            if lambda_irm > 0:
                irm_uq = compute_irm_penalty(logits_uq, y_uq)
                irm_cic = compute_irm_penalty(logits_cic, y_cic)
                loss_irm = lambda_irm * (irm_uq + irm_cic) / 2.0
            else:
                loss_irm = torch.tensor(0.0, device=DEVICE)

            # --- Extract latent embeddings WITH gradients ---
            z_uq_3d = model.aligner(x_uq, 'uq')   # (batch, 30, 64)
            z_cic_3d = model.aligner(x_cic, 'cic')  # (batch, 30, 64)

            # Mean-pool over time: (batch, 64)
            z_uq_mean = z_uq_3d.mean(dim=1)
            z_cic_mean = z_cic_3d.mean(dim=1)

            # --- Supervised Contrastive Loss (cross-domain) ---
            if lambda_supcon > 0:
                z_all = torch.cat([z_uq_mean, z_cic_mean], dim=0)  # (2*batch, 64)
                y_all = torch.cat([y_uq, y_cic], dim=0)            # (2*batch,)
                loss_supcon = lambda_supcon * supervised_contrastive_loss(
                    z_all, y_all, temperature=supcon_temperature)
            else:
                loss_supcon = torch.tensor(0.0, device=DEVICE)

            # --- Class-Conditional MMD (per-class alignment) ---
            if lambda_cmmd > 0:
                loss_cmmd = lambda_cmmd * class_conditional_mmd(
                    z_uq_mean, y_uq, z_cic_mean, y_cic,
                    num_classes=NUM_CLASSES, subsample=min(256, mmd_subsample))
            else:
                loss_cmmd = torch.tensor(0.0, device=DEVICE)

            # --- Global MMD (backward compat, default off) ---
            if lambda_mmd > 0:
                z_uq_flat = z_uq_3d.reshape(-1, LATENT_DIM)
                z_cic_flat = z_cic_3d.reshape(-1, LATENT_DIM)
                if z_uq_flat.size(0) > mmd_subsample:
                    idx = torch.randperm(z_uq_flat.size(0))[:mmd_subsample]
                    z_uq_flat = z_uq_flat[idx]
                if z_cic_flat.size(0) > mmd_subsample:
                    idx = torch.randperm(z_cic_flat.size(0))[:mmd_subsample]
                    z_cic_flat = z_cic_flat[idx]
                loss_mmd = lambda_mmd * mmd_loss(z_uq_flat, z_cic_flat)
            else:
                loss_mmd = torch.tensor(0.0, device=DEVICE)

            # --- Total loss ---
            total_loss = loss_ce + loss_irm + loss_supcon + loss_cmmd + loss_mmd

            optimizer.zero_grad()
            total_loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()

            epoch_ce += loss_ce.item()
            epoch_irm += loss_irm.item()
            epoch_mmd += loss_mmd.item()
            epoch_supcon += loss_supcon.item()
            epoch_cmmd += loss_cmmd.item()
            n_steps += 1

        # --- Validation ---
        model.eval()
        val_loss, vn = 0.0, 0
        with torch.no_grad():
            for loader, dtype in [(uq_val_loader, 'uq'), (cic_val_loader, 'cic')]:
                for x, y, _ in loader:
                    x, y = x.to(DEVICE), y.to(DEVICE)
                    loss = criterion(model(x, dtype), y)
                    val_loss += loss.item() * len(y)
                    vn += len(y)
        val_loss /= vn
        scheduler.step(val_loss)

        # Record history
        avg_ce = epoch_ce / max(n_steps, 1)
        avg_irm = epoch_irm / max(n_steps, 1)
        avg_mmd = epoch_mmd / max(n_steps, 1)
        avg_supcon = epoch_supcon / max(n_steps, 1)
        avg_cmmd = epoch_cmmd / max(n_steps, 1)
        history['ce'].append(avg_ce)
        history['irm'].append(avg_irm)
        history['mmd'].append(avg_mmd)
        history['supcon'].append(avg_supcon)
        history['cmmd'].append(avg_cmmd)
        history['total'].append(avg_ce + avg_irm + avg_mmd + avg_supcon + avg_cmmd)
        history['val_loss'].append(val_loss)
        history['lambda_irm'].append(lambda_irm)

        # Early stopping on val_loss
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_state = deepcopy(model.state_dict())
            patience_ctr = 0
        else:
            patience_ctr += 1

        if verbose and ((epoch + 1) % 5 == 0 or patience_ctr >= patience):
            print(f"  Epoch {epoch+1:3d} | CE: {avg_ce:.4f} | IRM: {avg_irm:.4f} | "
                  f"SC: {avg_supcon:.4f} | CMMD: {avg_cmmd:.4f} | "
                  f"Val: {val_loss:.4f} | λ_irm: {lambda_irm:.2f} | P: {patience_ctr}/{patience}")

        if patience_ctr >= patience:
            if verbose:
                print(f"  Early stopping at epoch {epoch+1}")
            break

    model.load_state_dict(best_state)
    return model, best_val_loss, history
