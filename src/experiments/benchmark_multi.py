#!/usr/bin/env python

from experiment import Experiment
import os
from helpers.subprocess_wrappers import check_output
from helpers import utils
import context
from router import Router
from trace import Trace
import math
import itertools
import traceback
import pandas as pd
from multiprocessing import Process, Lock
import arg_parser

class Benchmark():
    def __init__(self, schemelist, runs, runtime, delay_range, count, ramdisk = True, tmp_dir='./tmp_data', data_dir = './data', verbose=False):
            #loads all schemes after reboot
        for scheme in schemelist:
            check_output('python %s --schemes %s'%(os.path.join(context.src_dir, 'experiments/setup.py'), scheme), shell=True)

        self.routers = 11
        self.tmp_dir = tmp_dir
        self.data_dir = data_dir
        if ramdisk:
            utils.make_sure_dir_exists(self.tmp_dir)
            res = check_output('df -T %s'%self.tmp_dir, shell=True)
            if not 'tmpfs' in res: check_output('sudo mount -t tmpfs -o size=1500M tmpfs %s' % self.tmp_dir, shell=True)
            else: 
                print('%s is already a ramdisk' %self.tmp_dir)
        
        self.schemelist = schemelist
        self.runs = runs
        self.runtime = runtime
        self.delays = range(0,delay_range,50)
        self.count = count
        self.verbose = verbose
        self.build_experiments()
        
    def build_experiments(self):
        schemelist = self.schemelist
        delays = self.delays
        runs = self.runs
        runtime = self.runtime
        count = self.count
        routers = self.routers

        
        self.exp_res = self.build_rtt_experiments(schemelist)
        
        print('Expected runtime: %d seconds'%(runs*runtime*routers*len(delays)**2*2))

    def build_rtt_experiments(self, schemelist):
        schemelist = self.schemelist
        delays = self.delays
        runs = self.runs
        runtime = self.runtime
        count = self.count
        routers = self.routers
        
        rtt_unfairness_routers = [Router(delay=d) for d in delays]
        bottleneck_routers = self.build_router_range(12, 25, routers, range_factor=20)
        
        res = []
        rtts = []
        
        for i in range(len(schemelist)):
            rtt_str = 'rtt_' +  chr(ord('a')+i)
            rtts.append(rtt_str)
                       
        check_rtt = ''.join(str(e+', ') for e in rtts)

        #This is for appending scheme names to the output files
        scheme_arr = []
        for scheme in schemelist:
            schemes = str(count) + 'x'+ scheme + '_'
            scheme_arr.append(schemes)
        scheme_str = ''.join(str(f) for f in scheme_arr)

        for check_rtt in itertools.product(rtt_unfairness_routers, repeat=len(rtts)):
            #build an experiment for each combination of rtt routers
            flows = []
            
            #This is for appending rtts to the output files
            rtt_tup = []
            for i in range(len(check_rtt)):
                rtt_tup.append(check_rtt[i].args['delay'])
            tup_str = ''.join(str(r) for r in rtt_tup)

            for j in range(len(schemelist)):
                scheme = schemelist[j]
                flow = {'scheme':scheme, 'sender_router':check_rtt[j], 'count':count, 'flow_info':{'name':'%s_%d'%(scheme, check_rtt[j].args['delay'])}}
                flows.append(flow)
            
            exs = [  Experiment( scheme_str + tup_str + 'ms_queue%dB'%(q_size),
                  flows,
                  router,
                  runtime=runtime,
                  interval=0,
                  runs=runs,
                  tmp_dir=self.tmp_dir,
                  data_dir=self.data_dir)
                  for q_size, router in bottleneck_routers.items()]
            res.extend(exs)

        return res       

    def build_router_range(self, mbps, delay, num_routers, range_factor=10):
        """return a dict where
            values are routers with throughput 'mpbs' and delay 'delay' each, and queue sizes distributed logarithmically from bdp up to ranger_factor x bdp
            keys are the respectively used queue sizes"""
        bdp_bits = mbps*delay*1000.0*2
        bdp_bytes = bdp_bits/8
        step_size = 1.0/(num_routers-1)
        routers = {}
        nof_schemes = 2
        current_queue_size = int(bdp_bytes)

        #Use the below if you want to set queue sizes using the 'Stanford Model'
        #current_queue_size = int(bdp_bytes) / math.sqrt(nof_schemes)
        for i in range(num_routers):
            r = Router(delay=delay, up_trace=Trace(mbps=mbps), up_queue_type='droptail', up_queue_args = 'bytes=%d'%int(current_queue_size), down_trace=Trace(mbps=mbps))
            routers[int(current_queue_size)] = r
            current_queue_size *= math.pow(range_factor, step_size)
        return routers

    def run(self):
        ex_identifiers = ['ex_name', 'run_id']
        ex_parameters = ['bottleneck_tput', 'q_size']
        for i in range(len(self.schemelist)):
            scheme_str = 'scheme_' +  chr(ord('a')+i)
            ex_parameters.append(scheme_str)
             
        for i in range(len(self.schemelist)):
            rtprop_str = 'rtprop_' + chr(ord('a')+i)
            ex_parameters.append(rtprop_str)
            
        ex_parameters.append('runtime')
        
        ex_results = ['loss', 'interval_fairness', 'time_to_max_fairness', 'delay', 'throughput', 'duration'] + ['throughput_rsd%d'%i for i in range(1, 7)]
        results = pd.DataFrame(columns=ex_identifiers + ex_parameters + ex_results)
        for ex in self.exp_res:
            print('running experiment %s' % ex.experiment_name)
            try:
                with utils.nostdout(do_nothing=self.verbose):
                    ex.run()
                    ex_results = ex.plot()
                    for run_id, res in ex_results.items():
                        res.pop('stats')
                        data = {}
                        data['ex_name']=ex.experiment_name
                        data['run_id']=int(run_id)
                        data['bottleneck_tput']=ex.router.up_trace.mbps
                        data['bottleneck_rtprop']=2*ex.router.delay
                        data['q_size']=int(ex.router.up_queue_args.split('=')[1])
                        for i in range(len(self.schemelist)):
                            schemes = 'scheme_' +  chr(ord('a')+i)
                            data[schemes]=ex.flows[i]['scheme']
                        for i in range(len(self.schemelist)):
                            rtprops = 'rtprop_' + chr(ord('a')+i)
                            data[rtprops]=ex.flows[i]['sender_router'].delay
                        data['runtime']=ex.runtime
                        for flow_id, rsd in res.pop('throughput_relative_standard_deviation').items():
                            data['throughput_rsd%d'%flow_id]=rsd
                        for i in range(len(self.schemelist)):
                            scheme_tput = 'scheme_' + chr(ord('a')+i) + '_tput'
                            data[scheme_tput] = res['group_data'][i]['tput']
                        res.pop('group_data')                        
                        data.update(res)

                        results = results.append(data, ignore_index=True)

                    ex.cleanup_files()
            except Exception:
                with open(os.path.join(context.src_dir, 'experiments/exceptions.txt'), 'a+') as log:
                    traceback.print_exc(file=log)
                continue

        results.to_csv(path_or_buf=os.path.join(self.data_dir, 'results.csv'), index=False)   

if __name__ == '__main__':
    default_data_dir = os.path.join(context.src_dir, 'experiments/data')
    default_tmp_dir = os.path.join(context.src_dir, 'experiments/tmp_data')
    args = arg_parser.parse_benchmark(default_data_dir, default_tmp_dir)
    b = Benchmark(args.schemelist, args.runs, args.runtime, args.delay_range, args.count, ramdisk = not args.no_ramdisk, tmp_dir = args.tmp_dir, data_dir = args.data_dir, verbose = args.verbose)
    b.run()

