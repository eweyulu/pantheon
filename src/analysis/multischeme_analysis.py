"""
	Utility for plotting aggregated results of multiple schemes against eachother

"""

import pandas as pd
import matplotlib.pyplot as plt
import os
import numpy as np
import argparse

def plot_multischeme_summary(data_dirs, output_dir):
	plt.figure(1)
	fig1, ax1 = plt.subplots(num=1)
	fig1.suptitle('Fairness and RTT Dependency')
	plt.figure(2)
	fig2, ax2 = plt.subplots(num=2)
	fig2.suptitle('Loss and Queue Size')
	colors = list('rgbcmyk')
	for scheme_id, data_dir in enumerate(data_dirs):
		csv_path = os.path.join(data_dir, 'res_avg.csv')
		data = pd.read_csv(csv_path)
		scheme_a = data['scheme_a'].values[0]
		scheme_b = data['scheme_b'].values[0]
		solo = data.query('scheme_a==scheme_b')
		mixed = data.query('scheme_a!=scheme_b')
		for k, v in {'vs' :mixed, '':solo}.items():
#		for k, v in {'':solo}.items() + {'':mixed}.items():
			if len(v)==0: continue
			x_rtt = abs(v['rtprop_a'] - v['rtprop_b'])
			y_fair = v['overall_fairness']
			rtt_corr = np.corrcoef(x_rtt, y_fair)[0, 1]
			fairness = np.mean(y_fair)
			q_fraction = np.mean((v['mean_bottleneck_delay'] - (v['bottleneck_rtprop']/2))*v['bottleneck_tput']*1000.0/8.0/v['q_size'])
			loss = np.mean(v['loss'])
            
			if k=='':
				plt.figure(1)
				plt.plot(rtt_corr, fairness, 'o', label='%s %s'%(scheme_a, k), color=colors[scheme_id%len(colors)])
				plt.figure(2)
				plt.plot(q_fraction, loss, 'o', label='%s %s'%(scheme_a, k), color=colors[scheme_id%len(colors)])
			else:
				plt.figure(1)
				plt.plot(rtt_corr, fairness, 'x', label='%s vs %s'%(scheme_a, scheme_b), color=colors[scheme_id%len(colors)])
				plt.figure(2)
				plt.plot(q_fraction, loss, 'x', label='%s vs %s'%(scheme_a, scheme_b), color=colors[scheme_id%len(colors)])
	
	plt.figure(1)
	ax1.set_xlabel('Correlation coefficient of RTT unfairness and Fairness')
	ax1.set_ylabel('Total Fairness')
	plt.legend()
	plt.savefig(os.path.join(output_dir, 'fairness_rtt.pdf'))
	
	plt.figure(2)
	ax2.set_xlabel('Fraction of queue filled')
	ax2.set_ylabel('Loss rate')
	plt.legend()
	plt.savefig(os.path.join(output_dir, 'queue_loss.pdf'))


if __name__=='__main__':
	np.seterr(all='raise')
	parser = argparse.ArgumentParser()
	parser.add_argument('output_dir', type=str)
	parser.add_argument('data_dirs', nargs='+', type=str)
	args = parser.parse_args()
	plot_multischeme_summary(args.data_dirs, args.output_dir)

