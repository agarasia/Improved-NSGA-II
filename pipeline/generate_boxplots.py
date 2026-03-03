import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os

# --- CONFIGURATION ---
BASE_DIR = 'experiment_results'
SCRIPTS = ['NSGA-II-1', 'NSGA-II-2', 'NSGA-II-3']
K_VALUES = [1500, 3500, 5500, 7500, 9500]
K_TO_G = {1500: 7, 3500: 17, 5500: 27, 7500: 37, 9500: 47}
BUDGET_PCTS = range(10, 100, 10)

METRICS = {
    'hv': 'Hypervolume',
    'total_BV': 'Total Business Value',
    'pct_req_covered': 'Requirement Coverage (%)'
}

def create_boxplots():
    sns.set_theme(style="whitegrid")

    for k_val in K_VALUES:
        g_val = K_TO_G[k_val]
        print(f"Collecting data for Box Plots at K={k_val}...")
        
        all_raw_data = []

        for script_name in SCRIPTS:
            script_num = script_name.split('-')[-1]
            folder_name = f"nsga_ii_{script_num}_{k_val}"
            folder_path = os.path.join(BASE_DIR, folder_name)

            if not os.path.exists(folder_path):
                continue

            for pct in BUDGET_PCTS:
                filename = f"{script_name}_budget{pct}_K{k_val}.csv"
                file_path = os.path.join(folder_path, filename)

                if os.path.exists(file_path):
                    df = pd.read_csv(file_path)
                    # Use only raw runs (ignore the Average row)
                    raw_runs = df[df['seed'] != 'AVERAGE'].copy()
                    
                    # Add identifiers for plotting
                    raw_runs['Budget (%)'] = pct
                    if script_name == 'NSGA-II-1':
                        raw_runs['Algorithm'] = f"NSGA-II-1 (G={g_val})"
                    else:
                        raw_runs['Algorithm'] = script_name
                    
                    all_raw_data.append(raw_runs)

        if not all_raw_data:
            continue

        plot_df = pd.concat(all_raw_data, ignore_index=True)

        # Create a figure with 3 subplots (one for each metric)
        fig, axes = plt.subplots(3, 1, figsize=(14, 18))
        fig.suptitle(f'Distribution Analysis for K={k_val} (30 Repetitions)', fontsize=20, fontweight='bold')

        for i, (col_name, label) in enumerate(METRICS.items()):
            ax = axes[i]
            sns.boxplot(
                data=plot_df,
                x='Budget (%)',
                y=col_name,
                hue='Algorithm',
                palette='Set2',
                ax=ax
            )
            ax.set_title(f'Distribution of {label}', fontsize=15)
            ax.set_ylabel(label)
            ax.legend(title='Algorithm', loc='upper left', bbox_to_anchor=(1, 1))

        plt.tight_layout(rect=[0, 0.03, 0.9, 0.95])
        
        output_fig = f"boxplot_K{k_val}.png"
        plt.savefig(output_fig, dpi=300)
        print(f"  [SAVED] {output_fig}")
        plt.close()

if __name__ == "__main__":
    create_boxplots()