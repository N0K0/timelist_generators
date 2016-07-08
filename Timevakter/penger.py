import argparse
import re
import urllib2
from datetime import datetime, timedelta

paygrade_table = 'http://nikolasp.at.ifi.uio.no/C-tabell.csv'


class Penger:
    def get_hourly_rate(self):
        grade = self.config['paygrade']
        if self.config.get('rate', None) is not None:
            return self.config.get('rate')

        connection = urllib2.urlopen(paygrade_table).read().replace(',', '.')
        lines = connection.split('\n')

        if grade > 101:
            print "Dude, you are making waaay too much money (paygrade stops at 101)"
            self.config['rate'] = 0

        line = lines[grade - 19]
        self.config['rate'] = float(line.split(';')[2])

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
        self.args = parser.parse_args()

        print self.args

    def parse_config(self):
        config = open('.timerc', 'r')
        config_str = config.read()

        re_config = re.compile(ur'^(.*?):\s*(\S*).*?$', re.MULTILINE)

        config_res = re.findall(re_config, config_str)

        arg_number = 6
        if len(config_res) != arg_number:
            print "Error with .timerc file, wrong number of arguments found in the file\n" \
                  "Should be {0} arguments, found {1}". \
                format(arg_number, len(config_res))
            exit(1)

        for pair in config_res:
            self.config[pair[0]] = pair[1]

        self.config['tax percentage'] = float(self.config['tax percentage'])
        self.config['paygrade'] = int(self.config['paygrade'])

    def parse_timesheet(self):

        date_today = datetime.today()

        def date_range():
            if self.args.y and self.args.m:
                print "m/y found"
                date_start = datetime(self.args.y, self.args.m, 1)
                date_end = datetime(self.args.y, self.args.m + 1, 1)
                date_end = date_end - timedelta(seconds=1)
            elif self.args.m:
                print "month found"
                date_start = datetime(date_today.year, self.args.m, 1)
                date_end = datetime(date_start.year, self.args.m + 1, 1)
                date_end = date_end - timedelta(seconds=1)
            elif self.args.y:
                print "year found"
                date_start = datetime(self.args.y, 1, 1)
                date_end = datetime(self.args.y + 1, 1, 1)
                date_end = date_end - timedelta(seconds=1)
            else:
                print "nothing found"
                date_start = datetime(date_today.year, date_today.month, 1)
                date_end = datetime(date_today.year, date_today.month + 1, 1)
                date_end = date_end - timedelta(seconds=1)

            print "Start: {}\nEnd: {}".format(date_start, date_end)
            return date_start, date_end

        sheet_data = ''
        try:
            sheet = open(self.config.get('timesheet'), 'r')
            sheet_data = sheet.read()
        except IOError:
            print "Unable to open {} , check your .timerc file or the rights on the timesheet" \
                .format(self.config['timesheet'])

        re_sheet = re.compile(ur'(^[0-9- :]+)([ a-zA-Z]*)?(#[ \S]*$)?', re.MULTILINE)

        sheet_data = re.findall(re_sheet, sheet_data)
        date_range()
        for date in sheet_data:
            print date

    def __init__(self):
        self.config = {}
        self.args = None
        # NOTE: This is manually updated by Nikolasp, yell at him if he has forgotten to update the table

        self.parse_commands()
        self.parse_config()
        self.parse_timesheet()


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
