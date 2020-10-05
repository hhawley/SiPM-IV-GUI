import sys
from datetime import datetime
# Just holds the Logger class

# Not my code. Credits goes to
# https://stackoverflow.com/questions/14906764/how-to-redirect-stdout-to-both-file-and-console-with-scripting
class Logger(object):
    def __init__(self):
        self.terminal = sys.stdout

    def write(self, message):
        with open ("logfile.log", "a", encoding = 'utf-8') as self.log:            
            self.log.write(f'({datetime.now()}): {message}')
        self.terminal.write(message)

    def flush(self):
        #this flush method is needed for python 3 compatibility.
        #this handles the flush command by doing nothing.
        #you might want to specify some extra behavior here.
        pass