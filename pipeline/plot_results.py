import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os

# --- CONFIGURATION ---
BASE_DIR = 'experiment_results'
SCRIPTS = ['NSGA-II-1', 'NSGA-II-2', 'NSGA-II-3']
K_VALUES = [1500, 3500, 5500, 7500, 9500]
K_TO_G = {1500: 7, 3500: 17, 5500: 27, 7500: 37, 9500: 47}

METRICS = {
    'hv': 'Hypervolume',
    'total_BV': 'Total Business Value',
    'pct_req_covered': 'Requirement Coverage (%)',
    'wall_clock_time': 'Execution Time (seconds)'
}

def create_comparison_plots():
    sns.set_theme(style="whitegrid")
    
    for k_val in K_VALUES:
        g_val = K_TO_G[k_val]
        print(f"Generating comparison plots for K={k_val} (G={g_val})...")
        
        comparison_data = []
        
        # Collect data for this specific K level from every script
        for script_name in SCRIPTS:
            folder_name = f"{script_name.lower().replace('-', '_')}_{k_val}"
            file_path = os.path.join(BASE_DIR, folder_name, f"summary_{script_name}_K{k_val}.csv")
            
            if os.path.exists(file_path):
                df = pd.read_csv(file_path)
                
                # Label the algorithm for the legend
                if script_name == 'NSGA-II-1':
                    df['Algorithm'] = f"NSGA-II-1 (G={g_val})"
                else:
                    df['Algorithm'] = f"{script_name} (K={k_val})"
                
                comparison_data.append(df)
        
        if not comparison_data:
            print(f"No summary data found for K={k_val}. Skipping.")
            continue
            
        full_df = pd.concat(comparison_data, ignore_index=True)
        full_df['budget_pct'] = pd.to_numeric(full_df['budget_pct'])

        # Create 2x2 Plot
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        fig.suptitle(f'Algorithm Comparison at Eval Level: {k_val}', fontsize=20, fontweight='bold')
        
        axes_flat = axes.flatten()

        for i, (col_name, label) in enumerate(METRICS.items()):
            ax = axes_flat[i]
            
            sns.lineplot(
                data=full_df, 
                x='budget_pct', 
                y=col_name, 
                hue='Algorithm', 
                marker='o', 
                markersize=8,
                linestyle='dotted',
                linewidth=2,
                palette='Set1', # Bold colors for algorithm distinction
                ax=ax
            )
            
            ax.set_title(f'Budget vs {label}', fontsize=14)
            ax.set_xlabel('Budget Percentage (%)')
            ax.set_ylabel(label)
            ax.legend(title="Algorithm Version", loc='best')
            
        plt.tight_layout(rect=[0, 0.03, 1, 0.95])
        
        # Save one file per K-value
        output_fig = f"comparison_K{k_val}.png"
        plt.savefig(output_fig, dpi=300)
        print(f"Saved: {output_fig}")
        plt.show()

if __name__ == "__main__":
    create_comparison_plots()