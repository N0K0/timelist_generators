import fpdf
import argparse
import re
import urllib2

class Penger:

    config = {}

    def parse_commands(self):
        parser = argparse.ArgumentParser(description='Timeliste generator -- Nikolas Papaioannou <nikolasp@ifi.uio.no>'
                                         , prefix_chars='-/', version='0.1', epilog=epilog,
                                         formatter_class=argparse.RawTextHelpFormatter)
        parser.add_argument('-p', metavar='--printer', type=str, default=None, help='What printer to send the job to')
        parser.add_argument('-m', metavar='--month', type=int, default=None, help="What month to generate")
        parser.add_argument('-y', metavar='--year', type=int, default=None, help="What year to print")
        parser.add_argument('-e', metavar='--email', type=str, default=None,
                            help='NOT IMPLEMENTED - Address to send PDF')
        parser.add_argument('-o', metavar='--output', type=str, default=None, help="name of the PDF file")
        args = parser.parse_args()
        # print args

    def parse_config(self):

        config = open('.timerc', 'r')
        config_str = config.read()

        re_config = re.compile(ur'^(.*?):\s*(\S*).*?$', re.MULTILINE)

        config_res = re.findall(re_config, config_str)
        # print config_res

        argumentnumber = 6
        if len(config_res) != argumentnumber:
            print "Error with .timerc file, wrong number of arguments found in the file\nShould be {0} arguments, found {1}". \
                format(argumentnumber, len(config_res))
            exit(1)

        for pair in config_res:
            self.config[pair[0]] = pair[1]

    def __init__(self):

        # NOTE: This is manually updated by Nikolas, yell at him if he has forgotten to update the table
        self.paygrade_table = 'http://nikolasp.at.ifi.uio.no/C-tabell.csv'
        self.parse_commands()
        self.parse_config()

        connection = urllib2.urlopen(self.paygrade_table)
        comma = connection.read()

epilog = '''
Example of timesheet content:

    YYYY-MM-DD: hh:mm-hh:mm # commentary
    YYMMDD: hh-hh
    YYMM: tt # Javakurs
    YYMMDD: hh-hh # Langfredag


Formatting for the .timerc file:

    tax percentage: 5           # how much you are taxed
    paygrade:       40          # what paygrade you got
    timesheet:      ~/timer.txt # placement of your timesheet
    pnr:            12345123450 # leave blank if you do not wish this to be added
    posistion:      Timevakt    # name of your posistion
    place:          IFI         # place of work
'''

if __name__ == '__main__':
    penger = Penger()
