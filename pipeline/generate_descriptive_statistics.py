import pandas as pd
import os
import re

# --- CONFIGURATION ---
BASE_DIR = 'experiment_results'
SCRIPTS = ['NSGA-II-1', 'NSGA-II-2', 'NSGA-II-3']
K_VALUES = [1500, 3500, 5500, 7500, 9500]
BUDGET_PCTS = range(10, 100, 10)
OUTPUT_FILE = 'Experiment_Descriptive_Statistics.xlsx'

# Metrics to analyze
METRICS = ['hv', 'total_BV', 'pct_req_covered']

def get_stats():
    # Use ExcelWriter to save multiple sheets
    with pd.ExcelWriter(OUTPUT_FILE, engine='openpyxl') as writer:
        for script_name in SCRIPTS:
            print(f"Processing statistics for {script_name}...")
            all_configs_stats = []

            for k_val in K_VALUES:
                # Folder naming convention: nsga_ii_1_1500
                script_num = script_name.split('-')[-1]
                folder_name = f"nsga_ii_{script_num}_{k_val}"
                folder_path = os.path.join(BASE_DIR, folder_name)

                if not os.path.exists(folder_path):
                    continue

                for pct in BUDGET_PCTS:
                    # File naming convention: NSGA-II-1_budget10_K1500.csv
                    filename = f"{script_name}_budget{pct}_K{k_val}.csv"
                    file_path = os.path.join(folder_path, filename)

                    if os.path.exists(file_path):
                        df = pd.read_csv(file_path)
                        
                        # 1. Filter out the 'AVERAGE' row to get only the 30 raw runs
                        raw_runs = df[df['seed'] != 'AVERAGE'].copy()
                        
                        # Convert columns to numeric just in case
                        for m in METRICS:
                            raw_runs[m] = pd.to_numeric(raw_runs[m])

                        # 2. Calculate Descriptive Statistics
                        stats = raw_runs[METRICS].describe().transpose()
                        
                        # 3. Flatten the stats into a single row for this Budget/K combo
                        # We want columns like: hv_mean, hv_std, total_BV_mean, etc.
                        row_entry = {
                            'Budget (%)': pct,
                            'K / Generations': k_val if script_name != 'NSGA-II-1' else f"G={ (k_val//200)-1 if k_val > 200 else 7 }" # Approximation for label
                        }
                        
                        for metric in METRICS:
                            row_entry[f'{metric}_Mean'] = stats.loc[metric, 'mean']
                            row_entry[f'{metric}_Std'] = stats.loc[metric, 'std']
                            row_entry[f'{metric}_Median'] = raw_runs[metric].median()
                            row_entry[f'{metric}_Min'] = stats.loc[metric, 'min']
                            row_entry[f'{metric}_Max'] = stats.loc[metric, 'max']
                        
                        all_configs_stats.append(row_entry)

            if all_configs_stats:
                # Convert list of dicts to DataFrame
                sheet_df = pd.DataFrame(all_configs_stats)
                
                # Sort by K then Budget
                sheet_df = sheet_df.sort_values(by=['K / Generations', 'Budget (%)'])
                
                # Write to the specific sheet
                sheet_df.to_excel(writer, sheet_name=script_name, index=False)
                print(f"  [DONE] Sheet '{script_name}' created.")

    print(f"\nSuccessfully generated statistics at: {OUTPUT_FILE}")

if __name__ == "__main__":
    get_stats()