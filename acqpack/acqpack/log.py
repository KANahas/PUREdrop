import pandas as pd
import IPython.display as disp
import inspect
import types
import time
import threading
import os
import shutil
import hashlib

# TODO:
# - continously updating display with new events (flag?)
# - conditional formatting (pandas styler)
# - plotting
# - use python built-in logging backend (cross-notebook)?
# - logging/inspection from Jupyter? reproducable Juyter plugin?
# - fix signature of wrapper [e.g. f.goto(lookup, blah,...)]
# - keyword args
# - bug where __init__ time logging doesn't work properly
# - how to handle re-running cells/etc
# - single .track() function
# - simulation (on ordered scale, not necessarily time-based)
# - log state interpreter
# - get_state(log) 
# - config .show() to hide fields
# - thread safety https://stackoverflow.com/questions/261683/what-is-meant-by-thread-safe-code
# - 'cls' usage problem: https://stackoverflow.com/questions/4613000/what-is-the-cls-variable-used-for-in-python-classes
class Log():
    """
    Creates a pandas df for logging function calls.
    The columns of the df are:
    't_in','ts_in','t_out','ts_out','cl','fn','fn_in','fn_out'
    
    Provides functions for replacing:
     a) functions [.track_fn(f)]
     b) classes [.track_classes(classes)]
    with wrapped versions that log calls to the df.
    
    Example: ------------------------------
    l = Log()
    
    # create tracked function (1st way)
    @l.track_fn
    def f1(input):
        output = input
        return output
    
    # create tracked function (2nd way)
    def f2(input):
        output = input
        return output
    f2 = l.track_fn(f2)
    
    # replace classes with versions whose
    # functions are all tracked
    l.track_classes([Class1, Class2, ...])
    
    # manually write to log 
    l.write('A note')
    
    # make function calls as normal
    f1('input')
    f2('input')
    Class1.f('input')
    
    # display log
    l.show()
    
    # access log
    l.df
        
    """
    def __init__(self):
        self.df = pd.DataFrame(columns=['t_in', 'ts_in', 't_out', 'ts_out', 'dt', 'th',
                                        'cl', 'fn', 'fn_in', 'fn_out'])
        self.show_filter = 'index' # permissive filter
        self._lock = threading.Lock()
        self.write = self.track_fn(self.write)
        self.write('init')
    
    
    def format_time(self, time_s):
        return time.strftime("%Y%m%d_%H:%M:%S", time.localtime(time_s))
    
    
    def show(self, query='', ascending=True, clear_display=True):
        if query=='':
            query = self.show_filter

        ret = (self.df[['ts_in', 'ts_out', 'dt', 'th',
                       'cl', 'fn', 'fn_in', 'fn_out']]
                       .query(query)
                       .sort_index(ascending=ascending)
                       .style
                       .set_properties(**{'text-align': 'left'})
                       .set_table_styles([dict(selector='th', props=[('text-align', 'left')] ) ])
                       .format({'dt': "{:.3f}"}))
        if clear_display:
            disp.clear_output(wait=True)
            disp.display(ret)
        else:
            return ret.data
    
    def write(self, msg):
        pass
    
    def track_fn(self, f):
        def wrapper(*args):
            if f.__class__.__name__ == 'instancemethod':
                cl = f.im_class.__name__
                if cl!='Log':
                    inputs = args[1:]
                else:
                    inputs = args
            else:
                cl = ''
                inputs = args
            #obj = str(args[0])[str(args[0]).find('at ')+3:-1]
            fn = f.__name__
            
            with self._lock:
                i = len(self.df)
                t_in = time.time()
                th = threading.currentThread().getName()
                # print 'in', fn, threading.active_count()
                self.df.loc[i, ['t_in','ts_in','th','cl','fn','fn_in']] = [t_in, self.format_time(t_in), th, cl, fn, inputs]
            outputs = f(*args)
            with self._lock:
                t_out = time.time()
                self.df.loc[i, ['t_out','ts_out','dt','fn_out']] = [t_out, self.format_time(t_out), t_out-t_in, outputs]
                # print 'out', fn, threading.active_count()
            
            return outputs 
        wrapper.__doc__ = f.__doc__
        return wrapper
    
    def track_classes(self, classes):
        for cl in classes:
            for name, f in inspect.getmembers(cl):
                if isinstance(f, types.UnboundMethodType):
                    setattr(cl, name, self.track_fn(f))



class MyLogger():

    def __init__(self, logdir, overwrite = False) -> types.NoneType:
        self.logdir = logdir
        
        # check if directory exists
        if not overwrite:
            assert not os.path.isdir(self.logdir), f'Directory {self.logdir} exists. Either choose a different log directory, or set overwrite to True.'

        # overwrite directory if wanted
        if os.path.isdir(self.logdir):
            print('Log directory already exists. As overwrite is set to True, the existing directory will be deleted and overwritten.')
            shutil.rmtree(self.logdir)

        # make directory
        os.makedirs(logdir, exist_ok=True)

        # make logfile
        self.logfile = os.path.join(self.logdir, 'log.txt')
        self.log('CREATED LOGFILE', True)

        # make hasmap file
        self.hashmap = os.path.join(self.logdir, 'hashmap.txt')

    
    def log(self, logstring, tocmd=False):
        '''Set ptin=True if the logstring should also be printed to the command line.'''
        stamp_logstring = f'[{self.timestamp()}] {logstring}\n'
        open(self.logfile, 'a').write(stamp_logstring)
        if tocmd:
            print(stamp_logstring)

    def savefile(self, filepath):

        # make a hash string from the filepath
        hash_string = hashlib.md5(filepath.encode()).hexdigest()
        hash_filename = hash_string + '.' + filepath.split('.')[-1]
        self.log(f'Hashed file {filepath} as {hash_filename}.')

        # save translation to hash map
        open(self.hashmap, 'a').write(f'{filepath}\t{hash_filename}\n')

        new = os.path.join(self.logdir, hash_filename)
        shutil.copyfile(filepath, new)
        self.log(f'Saved file to {new}.', True)
        
    def timestamp(self):
        return time.strftime("%Y%m%d_%H:%M:%S")

