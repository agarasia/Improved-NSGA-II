import subprocess
import pandas as pd
import time
import os

# --- CONFIGURATION ---
INPUT_EXCEL = 'D1.xlsx'
TEMP_CSV = 'data_converted.csv'
REPS = 30
BUDGET_PCTS = range(10, 100, 10)  # 10%, 20% ... 90%
POP_SIZE = 200

BASE_OUTPUT_DIR = 'experiment_results'

PARAM_MAPPING = [
    {'K': 1500, 'G': 7},
    {'K': 3500, 'G': 17},
    {'K': 5500, 'G': 27},
    {'K': 7500, 'G': 37},
    {'K': 9500, 'G': 47}
]

def compute_hv_2d_max(pareto_rows, max_total_bv):
    if max_total_bv <= 0 or not pareto_rows:
        return 0.0
    points = []
    for r in pareto_rows:
        x = r['total_BV'] / max_total_bv
        y = r['pct_req_covered'] / 100.0
        points.append((x, y))
    points = sorted(set(points), reverse=True)
    nd = []
    best_y = -1
    for x, y in points:
        if y > best_y:
            nd.append((x, y))
            best_y = y
    hv = 0.0
    prev_y = 0.0
    for x, y in nd:
        if y > prev_y:
            hv += x * (y - prev_y)
            prev_y = y
    return hv

def run_pipeline():
    print(f"Reading {INPUT_EXCEL}...")
    df_raw = pd.read_excel(INPUT_EXCEL)
    df_raw.to_csv(TEMP_CSV, index=False)

    max_total_bv = df_raw.groupby('us_id')['us_businessvalue'].max().sum()
    total_test_time = df_raw.groupby('tc_id')['tc_executiontime'].max().sum()
    
    print(f"Starting Experiment Pipeline...")
    print(f"Max BV: {max_total_bv} | Total Time: {total_test_time:.2f}")

    

    for pct in BUDGET_PCTS:
        abs_budget = (pct / 100.0) * total_test_time
        
        for mapping in PARAM_MAPPING:
            K_val = mapping['K']
            G_val = mapping['G']
            
            for script in ['NSGA-II-1.py', 'NSGA-II-2.py', 'NSGA-II-3.py']:
                run_metrics = []
                
                # Format directory name: nsga_ii_1_1500, nsga_ii_2_1500, etc.
                script_num = script.split('-')[-1].replace('.py', '')
                folder_name = f"nsga_ii_{script_num}_{K_val}"
                current_output_dir = os.path.join(BASE_OUTPUT_DIR, folder_name)
                
                # Create the specific subfolder if it doesn't exist
                if not os.path.exists(current_output_dir):
                    os.makedirs(current_output_dir)

                script_label = script.replace('.py', '')
                final_filename = f"{script_label}_budget{pct}_K{K_val}.csv"
                final_path = os.path.join(current_output_dir, final_filename)
                
                print(f"Processing: {folder_name}/{final_filename}...", end="", flush=True)
                
                for seed in range(1, REPS + 1):
                    out_file = f"temp_seed_{seed}.csv"
                    
                    cmd = [
                        "python3", script, 
                        "--input", TEMP_CSV,
                        "--budget", str(abs_budget),
                        "--pop", str(POP_SIZE),
                        "--seed", str(seed),
                        "--out", out_file
                    ]
                    
                    if script == 'NSGA-II-1.py':
                        cmd += ["--gens", str(G_val)]
                    else:
                        cmd += ["--eval_budget", str(K_val), "--gens", "1000"]

                    start_wall = time.perf_counter()
                    subprocess.run(cmd, capture_output=True)
                    end_wall = time.perf_counter()
                    
                    duration = end_wall - start_wall
                    
                    if os.path.exists(out_file):
                        res_df = pd.read_csv(out_file)
                        if not res_df.empty:
                            pareto_rows = res_df.to_dict('records')
                            hv_value = compute_hv_2d_max(pareto_rows, max_total_bv)
                            best_sol = res_df.sort_values('total_BV', ascending=False).iloc[0]
                            run_metrics.append({
                                'seed': seed,
                                'hv': hv_value,
                                'total_BV': best_sol['total_BV'],
                                'pct_req_covered': best_sol['pct_req_covered'],
                                'total_time_used': best_sol['total_time'],
                                'wall_clock_time': duration
                            })
                        os.remove(out_file)

                if run_metrics:
                    config_df = pd.DataFrame(run_metrics)
                    averages = config_df.mean().to_dict()
                    averages['seed'] = 'AVERAGE'
                    config_df = pd.concat([config_df, pd.DataFrame([averages])], ignore_index=True)
                    config_df.to_csv(final_path, index=False)
                    print(f" DONE")

    print("\n" + "="*30)
    print(f"ALL RUNS COMPLETE. Files organized in '{BASE_OUTPUT_DIR}/'.")

if __name__ == "__main__":
    run_pipeline()