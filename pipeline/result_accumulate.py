import pandas as pd
import os
import re

# --- CONFIGURATION ---
BASE_DIR = 'experiment_results'
SCRIPTS = ['NSGA-II-1', 'NSGA-II-2', 'NSGA-II-3']
K_VALUES = [1500, 3500, 5500, 7500, 9500]

def accumulate():
    for script_name in SCRIPTS:
        for k_val in K_VALUES:
            # Path to the specific script and K folder
            # e.g., experiment_results/nsga_ii_1_1500/
            folder_path = os.path.join(BASE_DIR, f"{script_name.lower().replace('-', '_')}_{k_val}")
            
            if not os.path.exists(folder_path):
                print(f"Skipping missing folder: {folder_path}")
                continue

            summary_data = []
            
            # Look for all budget files in this specific K folder
            # Matches: NSGA-II-1_budget10_K1500.csv, etc.
            files = [f for f in os.listdir(folder_path) if f.startswith(f"{script_name}_budget")]
            
            # Sort files by budget percentage numerically
            files.sort(key=lambda x: int(re.search(r'budget(\d+)', x).group(1)))

            for filename in files:
                file_path = os.path.join(folder_path, filename)
                
                # Extract budget % from filename for the summary table
                budget_pct = re.search(r'budget(\d+)', filename).group(1)
                
                try:
                    df = pd.read_csv(file_path)
                    
                    # Locate the row where 'seed' column is 'AVERAGE'
                    avg_row = df[df['seed'] == 'AVERAGE'].copy()
                    
                    if not avg_row.empty:
                        # Add a column to identify which budget this average belongs to
                        avg_row.insert(0, 'budget_pct', budget_pct)
                        summary_data.append(avg_row)
                except Exception as e:
                    print(f"Error reading {filename}: {e}")

            # 3. Create the summary file if data exists
            if summary_data:
                final_summary_df = pd.concat(summary_data, ignore_index=True)
                
                # Clean up: Remove the original 'seed' column as it just says 'AVERAGE'
                final_summary_df = final_summary_df.drop(columns=['seed'])
                
                output_path = os.path.join(folder_path, f"summary_{script_name}_K{k_val}.csv")
                final_summary_df.to_csv(output_path, index=False)
                print(f"Created summary for {script_name} K={k_val} at: {output_path}")

if __name__ == "__main__":
    accumulate()