"""
Auto-Response module: block attacker IPs via VPC Network ACL.
Uses NACL DENY rules to block traffic from detected attacker source IPs.
"""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# NACL rule numbers 50-99 reserved for auto-block (lower = higher priority)
BLOCK_RULE_START = 50
BLOCK_RULE_END = 99
MAX_BLOCKS = BLOCK_RULE_END - BLOCK_RULE_START + 1


@dataclass
class BlockRecord:
    ip: str
    rule_number: int
    blocked_at: str
    reason: str
    attack_class: str
    confidence: float


class AutoResponseManager:
    """Manages attacker IP blocking via VPC Network ACL."""

    def __init__(self):
        self._blocked: dict[str, BlockRecord] = {}
        self._nacl_id: str | None = os.environ.get("VICTIM_NACL_ID")
        self._enabled: bool = os.environ.get("AUTO_RESPONSE_ENABLED", "true").lower() == "true"
        self._confidence_threshold: float = float(os.environ.get("BLOCK_CONFIDENCE_THRESHOLD", "0.85"))
        self._min_alerts: int = int(os.environ.get("BLOCK_MIN_ALERTS", "3"))
        self._alert_counts: dict[str, int] = {}
        # Allowlist: never block these IPs (VPC internal, sensor, engine, etc.)
        self._allowlist: set[str] = set()
        allowlist_str = os.environ.get("ALLOWLIST_IPS", "10.0.0.0/8")
        for item in allowlist_str.split(","):
            self._allowlist.add(item.strip())

        region = os.environ.get("AWS_REGION", "ap-southeast-1")
        try:
            self._ec2 = boto3.client("ec2", region_name=region)
        except Exception:
            self._ec2 = None
            logger.warning("boto3 EC2 client unavailable — auto-response disabled")

    @property
    def enabled(self) -> bool:
        return self._enabled and self._ec2 is not None and self._nacl_id is not None

    def _is_allowlisted(self, ip: str) -> bool:
        """Check if IP is in allowlist (private ranges by default)."""
        for entry in self._allowlist:
            if "/" in entry:
                # Simple prefix check for CIDR
                prefix = entry.split("/")[0]
                parts = prefix.split(".")
                ip_parts = ip.split(".")
                # Compare matching octets
                cidr = int(entry.split("/")[1])
                octets = cidr // 8
                if ip_parts[:octets] == parts[:octets]:
                    return True
            elif ip == entry:
                return True
        return False

    def record_alert(self, source_ip: str, attack_class: str, confidence: float) -> BlockRecord | None:
        """Record an alert for a source IP. Auto-block if thresholds met."""
        if not self.enabled or not source_ip or self._is_allowlisted(source_ip):
            return None

        if source_ip in self._blocked:
            return None  # Already blocked

        self._alert_counts[source_ip] = self._alert_counts.get(source_ip, 0) + 1

        if confidence >= self._confidence_threshold and self._alert_counts[source_ip] >= self._min_alerts:
            return self.block_ip(source_ip, attack_class, confidence)

        return None

    def block_ip(self, ip: str, attack_class: str = "Unknown", confidence: float = 0.0) -> BlockRecord | None:
        """Block an IP by adding DENY rule to NACL."""
        if ip in self._blocked:
            return self._blocked[ip]

        if len(self._blocked) >= MAX_BLOCKS:
            logger.warning(f"Max blocks ({MAX_BLOCKS}) reached, cannot block {ip}")
            return None

        rule_number = self._next_rule_number()
        if rule_number is None:
            return None

        cidr = f"{ip}/32"

        try:
            # Add ingress DENY rule
            self._ec2.create_network_acl_entry(
                NetworkAclId=self._nacl_id,
                RuleNumber=rule_number,
                Protocol="-1",  # All protocols
                RuleAction="deny",
                Egress=False,
                CidrBlock=cidr,
            )
            logger.info(f"Blocked {ip} via NACL rule #{rule_number}")

            record = BlockRecord(
                ip=ip,
                rule_number=rule_number,
                blocked_at=datetime.now(timezone.utc).isoformat(),
                reason=f"Auto-blocked: {attack_class} (confidence: {confidence:.2f})",
                attack_class=attack_class,
                confidence=confidence,
            )
            self._blocked[ip] = record
            return record

        except ClientError as e:
            logger.error(f"Failed to block {ip}: {e}")
            return None

    def unblock_ip(self, ip: str) -> bool:
        """Remove block for a specific IP."""
        if ip not in self._blocked:
            return False

        record = self._blocked[ip]
        try:
            self._ec2.delete_network_acl_entry(
                NetworkAclId=self._nacl_id,
                RuleNumber=record.rule_number,
                Egress=False,
            )
            del self._blocked[ip]
            self._alert_counts.pop(ip, None)
            logger.info(f"Unblocked {ip} (rule #{record.rule_number})")
            return True
        except ClientError as e:
            logger.error(f"Failed to unblock {ip}: {e}")
            return False

    def unblock_all(self) -> int:
        """Remove all auto-block NACL rules."""
        count = 0
        for ip in list(self._blocked.keys()):
            if self.unblock_ip(ip):
                count += 1
        return count

    def get_blocked(self) -> list[dict]:
        return [
            {
                "ip": r.ip,
                "rule_number": r.rule_number,
                "blocked_at": r.blocked_at,
                "reason": r.reason,
                "attack_class": r.attack_class,
                "confidence": r.confidence,
            }
            for r in self._blocked.values()
        ]

    def is_blocked(self, ip: str) -> bool:
        return ip in self._blocked

    def _next_rule_number(self) -> int | None:
        used = {r.rule_number for r in self._blocked.values()}
        for n in range(BLOCK_RULE_START, BLOCK_RULE_END + 1):
            if n not in used:
                return n
        return None
