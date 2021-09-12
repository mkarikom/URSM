#!/bin/bash

# python 2.7 environment 
# export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/dfs6/pub/mkarikom/binaries/anaconda3/lib/ # needed for pypolyagamma
# module load python/2.7.17 # needed for ursm, pypolyagamma

export ursmScript=/dfs6/pub/mkarikom/code/DTMwork/slurm/URSM/scUnif_LinuxEnv.py # main ursm script

export single_cell_expr_file=/dfs6/pub/mkarikom/code/URSM/demo/demo_data/demo_single_cell_rnaseq_counts.csv
export single_cell_type_file=/dfs6/pub/mkarikom/code/URSM/demo/demo_data/demo_single_cell_types.csv
export bulk_expr_file=/dfs6/pub/mkarikom/code/URSM/demo/demo_data/demo_bulk_rnaseq_counts.csv
export number_of_cell_types=3
export burn_in_length=50
export gibbs_sample_number=50
export EM_maxiter=50
export output_prefix=gemout_
export output_directory=/dfs6/pub/mkarikom/code/URSM/ms_demos
export ursmlog=dfs6/pub/mkarikom/code/URSM/ms_demos/demo.log

python $ursmScript