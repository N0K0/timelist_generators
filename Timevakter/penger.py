import fpdf
import argparse

class Penger:

    def parse_commands(self):
        parser = argparse.ArgumentParser(description='Timeliste generator',prefix_chars='-/',version='0.1')
        parser.add_argument('-p',metavar='--printer',type=str,default=None,help='What printer to send the job to')
        parser.add_argument('-m',metavar='--month',type=int,default=-1,help="What month to generate")
        parser.add_argument('-y',metavar='--year',type=int,default=-1,help="What year to print")
        parser.add_argument('-e',metavar='--email',type=str,default='',help='NOT IMPLEMENTED - Address to send PDF')
        args = parser.parse_args()

    def __init__(self):
        self.parse_commands()


if __name__ == '__main__':
    penger = Penger()
