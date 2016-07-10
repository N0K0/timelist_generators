import argparse
import re
import urllib2
import sys
from fpdf import FPDF
from datetime import datetime, timedelta

paygrade_table = 'http://nikolasp.at.ifi.uio.no/C-tabell.csv'
sys.tracebacklimit=1

class DateError(Exception):
    def __init__(self,message):
        self.message = message

    def __str__(self):
        return repr(self.message)


class PDF(FPDF):
    def header(self):
        #Logo
        self.image('uio_seal_a_eng.png',h=15,)
        self.set_font('Helvetica', 'B', 18)
        self.cell(140,ln=0)
        self.cell(40,h=-12,txt='Timesheet',ln=1)
        # Line break
        self.ln(20)




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

        re_config = re.compile(ur'(.*?):\s*([\\\~.\/0-9a-zA-Z ]*)(\#|$)', re.MULTILINE)

        config_res = re.findall(re_config, config_str)

        arg_number = 7
        if len(config_res) != arg_number:
            print "Error with .timerc file, wrong number of arguments found in the file\n" \
                  "Should be {0} arguments, found {1}". \
                format(arg_number, len(config_res))
            exit(1)

        for pair in config_res:
            self.config[pair[0]] = pair[1]

        self.config['tax percentage'] = float(self.config['tax percentage'])
        self.config['paygrade'] = int(self.config['paygrade'])

    def parse_date(self,date_str):
        for date_format in date_str_formats:
            try:
                return datetime.strptime(date_str, date_format) + timedelta(seconds=1)
            except ValueError:
                pass

        print "Error parsing the following date: {}".format(date_str)
        exit(1)

    def parse_hours(self,hour_str):
        for hour_format in hour_str_formats:
            try:
                return datetime.strptime(hour_str, hour_format)
            except ValueError:
                pass

        print "Error parsing the following timerange: {}".format(hour_str)
        exit(1)

    def get_hours(self,hour_str):
        print hour_str
        p = re.compile(ur':(.*)$', re.MULTILINE)

        time_res = re.search(p,hour_str)
        time_str = str(time_res.groups(0)[0]).strip()
        time_str = time_str.split('-')
        time_from, time_to = self.parse_hours(time_str[0]),self.parse_hours(time_str[1])
        time_delta = time_to-time_from

        hour_sum = time_delta.total_seconds()/3600

        return hour_sum,time_from,time_to


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

        date_start,date_end = date_range()

        self.filtered_entires = []
        self.sum_hour = 0

        for entry in sheet_data:
            #print entry
            entry_date = entry[0].split(':')[0]
            parsed_date = self.parse_date(entry_date)
            if date_start <= parsed_date <= date_end:
                self.filtered_entires.append(entry)

    def generate_PDF(self):
        pdf = PDF()
        pdf.add_page()

        pdf.set_font('Arial')
        pdf.multi_cell(w=100, h=8, txt="Name: {0}\nStilling: {1}\nPaygrade: {2}\nPlace of work: {3}\nSSN: {4}"
                       .format(self.config['name'], self.config['position'], self.config['paygrade'],
                               self.config['place'],
                               self.config['pnr']), align='L',)

        pdf.ln(10)
        #Done creating info and toptext

        #Starting to create cells
        #Creating the header
        pdf.set_font('Arial',size=12)
        cell_height = 6
        time_size = 20
        note_size = 74
        sign_size = 30

        pdf.cell(25,cell_height*2,txt="Date",border=1,ln=0,align='C')
        pdf.cell(20,cell_height*2,txt="Week",border=1,ln=0,align='C')
        pdf.cell(time_size*2,cell_height,txt="Time",border=1,ln=2,align='C')

        x,y = pdf.get_x(),pdf.get_y()

        pdf.cell(time_size,cell_height,txt="From",border=1,ln=0,align='C')
        pdf.cell(time_size,cell_height,txt="To",border=1,align='C')
        pdf.set_xy(x+time_size*2,y-cell_height)
        pdf.cell(note_size,cell_height*2,txt="Notes",border=1,ln=0,align='C')
        #TODO: Remember to stuff total hours into this field too
        pdf.cell(sign_size,cell_height*2,txt="Sign",border=1,ln=1,align='C')

        #Done creating top row
        pdf.set_font('Arial',size=12,style='b')

        for entry in self.filtered_entires:
            entry_date = entry[0].split(':')
            datetime_obj = self.parse_date(entry_date[0])
            datetime_str = datetime_obj.strftime('%Y-%m-%d')

            week_num = str(datetime_obj.isocalendar()[1])

            time_sum,time_from,time_to = self.get_hours(entry[0])
            print time_sum,time_from,time_to

            time_from = time_from.strftime('%H:%M')
            time_to = time_to.strftime('%H:%M')

            self.sum_hour += time_sum
            print self.sum_hour

            pdf.cell(25,cell_height,txt=datetime_str,ln=0,border=1,align='C') #Date cell
            pdf.cell(20,cell_height,txt=week_num,ln=0,border=1,align='C') #Wekk number cell
            pdf.cell(time_size,cell_height,border=1,txt=time_from) #From time
            pdf.cell(time_size,cell_height,border=1,txt=time_to) #To time
            pdf.cell(note_size,cell_height,border=1,txt=str(entry[2])) #Notes
            pdf.cell(sign_size,cell_height,border=1,ln=1)


        #After writing all the entries, we have an other entry as a note with the number of hours total

        pdf.cell(25, cell_height, ln=0, border=0, align='C')  # Date cell
        pdf.cell(20, cell_height, ln=0, border=0, align='C')  # Wekk number cell
        pdf.cell(time_size, cell_height, border=0)  # From time
        pdf.cell(time_size, cell_height, border=0)  # To time
        pdf.cell(note_size, cell_height, border=1,txt="Total hours: {}".format(self.sum_hour))  # Notes
        pdf.cell(sign_size, cell_height, border=0, ln=1)

        pdf.output('test.pdf')

    def __init__(self):
        self.config = {}
        self.args = None
        # NOTE: This is manually updated by Nikolasp, yell at him if he has forgotten to update the table

        self.parse_commands()
        self.parse_config()
        self.parse_timesheet()
        self.generate_PDF()



date_str_formats = ['%Y-%m-%d','%y%m','%y%m%d']
hour_str_formats = ['%H:%M', '%H']

epilog = '''
Example of timesheet content:

    YYYY-MM-DD: hh:mm-hh:mm # commentary
    YYMM: tt # Javakurs
    YYMMDD: hh-hh # Langfredag


Formatting for the .timerc file:
    name:           Nikolas Papaioannou
    tax percentage: 5           # how much you are taxed
    paygrade:       40          # what paygrade you got
    timesheet:      ~/timer.txt # placement of your timesheet
    pnr:            12345123450 # leave blank if you do not wish this to be added
    posistion:      Timevakt    # name of your posistion
    place:          IFI         # place of work
'''

if __name__ == '__main__':
    penger = Penger()
