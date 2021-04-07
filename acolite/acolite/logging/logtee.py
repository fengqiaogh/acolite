import os, sys, datetime
## object for logging stdout to log file when processing
class LogTee(object):

        def __init__(self, name):
            self.name=name
            ## make new file
            if os.path.exists(os.path.dirname(self.name)) is False:
                os.makedirs(os.path.dirname(self.name))
            self.file = open(self.name, 'w')
            self.file.close()
            self.mode='a'
            self.stdout = sys.stdout
            sys.stdout = self
        def __del__(self):
            sys.stdout = self.stdout
        def write(self, data):
            self.stdout.write(data)
            data = data.strip()
            if len(data) > 0:
                self.file = open(self.name, self.mode)
                self.file.write('{}: {}\n'.format(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),data))
                self.file.close()
        def flush(self):
            pass
