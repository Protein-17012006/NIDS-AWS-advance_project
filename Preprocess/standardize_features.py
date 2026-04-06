import pandas as pd

# Column mapping to standardize CIC-IDS2018 dataset to match CIC-IDS2017 standardized format
# This mapping aligns the 2018 dataset column names with the 2017 standardized names
column_mapping_2018 = {
    'Fwd Pkts/s': 'Fwd Packets/s',
    'Bwd Pkts/s': 'Bwd Packets/s'
}

# Read the input Parquet file
df = pd.read_parquet('/home/huyho/earth_predict_env/dataset/Dataset_cic_2018/cic2018_balanced_dataset.parquet')

# Rename columns to match 2017 standardized format
df_renamed = df.rename(columns=column_mapping_2018)

# Add missing column 'Fwd Header Length.1' if it doesn't exist (set to 0 or copy from 'Fwd Header Len')
if 'Fwd Header Length.1' not in df_renamed.columns:
    df_renamed['Fwd Header Length.1'] = df_renamed['Fwd Header Len']

# Reorder columns to match 2017 standardized format (put 'Fwd Header Length.1' after 'Bwd Seg Size Avg')
# Get the column order from 2017 standardized file
cols_2017_order = ['Dst Port', 'Flow Duration', 'Tot Fwd Pkts', 'Tot Bwd Pkts', 'TotLen Fwd Pkts', 
                    'TotLen Bwd Pkts', 'Fwd Pkt Len Max', 'Fwd Pkt Len Min', 'Fwd Pkt Len Mean', 
                    'Fwd Pkt Len Std', 'Bwd Pkt Len Max', 'Bwd Pkt Len Min', 'Bwd Pkt Len Mean', 
                    'Bwd Pkt Len Std', 'Flow Byts/s', 'Flow Pkts/s', 'Flow IAT Mean', 'Flow IAT Std', 
                    'Flow IAT Max', 'Flow IAT Min', 'Fwd IAT Tot', 'Fwd IAT Mean', 'Fwd IAT Std', 
                    'Fwd IAT Max', 'Fwd IAT Min', 'Bwd IAT Tot', 'Bwd IAT Mean', 'Bwd IAT Std', 
                    'Bwd IAT Max', 'Bwd IAT Min', 'Fwd PSH Flags', 'Bwd PSH Flags', 'Fwd URG Flags', 
                    'Bwd URG Flags', 'Fwd Header Len', 'Bwd Header Len', 'Fwd Packets/s', 'Bwd Packets/s', 
                    'Pkt Len Min', 'Pkt Len Max', 'Pkt Len Mean', 'Pkt Len Std', 'Pkt Len Var', 
                    'FIN Flag Cnt', 'SYN Flag Cnt', 'RST Flag Cnt', 'PSH Flag Cnt', 'ACK Flag Cnt', 
                    'URG Flag Cnt', 'CWE Flag Count', 'ECE Flag Cnt', 'Down/Up Ratio', 'Pkt Size Avg', 
                    'Fwd Seg Size Avg', 'Bwd Seg Size Avg', 'Fwd Header Length.1', 'Fwd Byts/b Avg', 
                    'Fwd Pkts/b Avg', 'Fwd Blk Rate Avg', 'Bwd Byts/b Avg', 'Bwd Pkts/b Avg', 
                    'Bwd Blk Rate Avg', 'Subflow Fwd Pkts', 'Subflow Fwd Byts', 'Subflow Bwd Pkts', 
                    'Subflow Bwd Byts', 'Init Fwd Win Byts', 'Init Bwd Win Byts', 'Fwd Act Data Pkts', 
                    'Fwd Seg Size Min', 'Active Mean', 'Active Std', 'Active Max', 'Active Min', 
                    'Idle Mean', 'Idle Std', 'Idle Max', 'Idle Min', 'Label']

# Keep extra columns from 2018 (Protocol, Timestamp) at the beginning
extra_cols = [col for col in df_renamed.columns if col not in cols_2017_order]
ordered_cols = extra_cols + [col for col in cols_2017_order if col in df_renamed.columns]
df_final = df_renamed[ordered_cols]

# Save the standardized Parquet file
output_path = '/home/huyho/earth_predict_env/dataset/Dataset_cic_2018/cic2018_balanced_dataset_standardized.parquet'
df_final.to_parquet(output_path, index=False)

# Show columns that were renamed
for old_name, new_name in column_mapping_2018.items():
    if old_name in df.columns:
        print(f"'{old_name}' -> '{new_name}'")

