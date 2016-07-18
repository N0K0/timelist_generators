#!/usr/bin/python
import argparse
import math
import os
import re
import shlex
import sys
import urllib2
from datetime import datetime, timedelta
from subprocess import Popen, PIPE
import getpass
import socket
import tempfile

sys.tracebacklimit = 1

try:
    from fpdf import FPDF
except ImportError as err:
    FPDF = None
    print 'Unable to import fpdf, please download the package'
    print 'NOTE: On uio? You can use \'pip install --user fpdf\'\n'\
          'to install without locally without the need of Sudo'
    raise err

# NOTE: This is manually updated by Nikolasp, yell at him if he has forgotten to update the table
pay_grade_table = 'http://nikolasp.at.ifi.uio.no/C-tabell.csv'
timerc_example_url = 'http://nikolasp.at.ifi.uio.no/timerc'
uio_logo_url = 'http://nikolasp.at.ifi.uio.no/uio_logo.png'

class DateError(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return repr(self.message)


class PDF(FPDF):
    def header(self):
        # Logo
        logo = urllib2.urlopen(uio_logo_url).read()
        temp = tempfile.NamedTemporaryFile(suffix=".png",delete=False)
        temp.write(logo)
        temp.close()
        self.image(temp.name, h=15)
        self.set_font('Helvetica', 'B', 18)
        self.cell(140, ln=0)
        self.cell(40, h=-12, txt='Timesheet', ln=1)
        self.ln(20)


class Penger:
    def get_hourly_rate(self):
        grade = self.config['pay grade']

        connection = urllib2.urlopen(pay_grade_table).read().replace(',', '.')
        lines = connection.split('\n')

        if grade < 19:
            print "Your pay grade is lower than what UiO generally allows... Somethings is wrong here"
            self.config['rate'] = 0

        if grade > 101:
            print "Dude, you are making waaay too much money (pay grade stops at 101)"
            self.config['rate'] = 0

        line = lines[grade - 19]
        self.config['rate'] = float(line.split(';')[2])

        return self.config['rate']

    def parse_commands(self):
        parser = argparse.ArgumentParser(description='Timeliste generator -- Nikolas Papaioannou <nikolasp@ifi.uio.no>'
                                         , prefix_chars='-/', epilog=str(timesheet_example) + str(timerc_example),
                                         formatter_class=argparse.RawTextHelpFormatter)
        parser.add_argument('-p', metavar='--printer', type=str, default=None, help='What printer to send the job to')
        parser.add_argument('-m', metavar='--month', type=int, default=None, help="What month to generate")
        parser.add_argument('-y', metavar='--year', type=int, default=None, help="What year to print")
        parser.add_argument('-e', metavar='--email', type=str, default=None,
                            help='Address to send PDF')
        parser.add_argument('-o', metavar='--output', type=str, default=None, help="name of the PDF file")
        self.args = parser.parse_args()

    def parse_config(self):

        if not os.path.exists('.timerc'):

            print "NOTE: Was unable to find your .timerc file, so made a new one at {0}"\
                .format(os.path.abspath('.timerc'))

            example = urllib2.urlopen(timerc_example_url).read()
            config = open('.timerc', 'w')
            config.write(example)
            config.close()

        try:
            config = open('.timerc', 'r')
            config_str = config.read()

            re_config = re.compile(ur'(.*?):\s+([_\\~.\/0-9a-zA-Z ]*)(#.*$|$)', re.MULTILINE)

            config_res = re.findall(re_config, config_str)

            arg_number = 7
            if len(config_res) != arg_number:
                print "Error with .timerc file, wrong number of arguments found in the file\n" \
                      "Should be {0} arguments, found {1}". \
                    format(arg_number, len(config_res))

                print timerc_example

                exit(1)

            for pair in config_res:
                self.config[pair[0]] = pair[1].strip()

            self.config['tax percentage'] = float(self.config['tax percentage'])
            self.config['pay grade'] = int(self.config['pay grade'])
        except IOError:
            print "Unable to find a .timerc file, creating an example file for you"



    @staticmethod
    def parse_date(date_str):
        for date_format in date_str_formats:
            try:
                return datetime.strptime(date_str, date_format) + timedelta(seconds=1)
            except ValueError:
                pass

        print "Error parsing the following date: {0}".format(date_str)
        exit(1)

    @staticmethod
    def parse_hours(hour_str):
        for hour_format in hour_str_formats:
            try:
                return datetime.strptime(hour_str, hour_format)
            except ValueError:
                pass

        print "Error parsing the following timerange: {0}".format(hour_str)
        exit(1)

    def get_hours(self, hour_str):
        p = re.compile(ur':(.*)$', re.MULTILINE)

        time_res = re.search(p, hour_str)
        time_str = str(time_res.groups(0)[0]).strip()
        time_str = time_str.split('-')
        if len(time_str) == 1:
            time_from = None
            time_to = None
            hour_sum = int(time_str[0])
        else:
            time_from, time_to = self.parse_hours(time_str[0]), self.parse_hours(time_str[1])
            time_delta = time_to - time_from
            #Using this janky shit of an formula since UiO has an outdates timedate module (total_sec is not implmented)
            hour_sum = (time_delta.microseconds + (time_delta.seconds + time_delta.days * 24 * 3600) * 10**6) / 10**6 / 3600

        return hour_sum, time_from, time_to

    def parse_timesheet(self):

        date_today = datetime.today()

        # noinspection PyShadowingNames
        def date_range():
            if self.args.y and self.args.m:
                date_start = datetime(self.args.y, self.args.m, 1)
                date_end = datetime(self.args.y, self.args.m + 1, 1)
                date_end = date_end - timedelta(seconds=1)
            elif self.args.m:
                date_start = datetime(date_today.year, self.args.m, 1)
                date_end = datetime(date_start.year, self.args.m + 1, 1)
                date_end = date_end - timedelta(seconds=1)
            elif self.args.y:
                date_start = datetime(self.args.y, 1, 1)
                date_end = datetime(self.args.y + 1, 1, 1)
                date_end = date_end - timedelta(seconds=1)
            else:
                date_start = datetime(date_today.year, date_today.month, 1)
                date_end = datetime(date_today.year, date_today.month + 1, 1)
                date_end = date_end - timedelta(seconds=1)

            return date_start, date_end

        sheet_data = ''
        try:
            path = os.path.expanduser(self.config['timesheet'])
            sheet = open(path, 'r')
            sheet_data = sheet.read()
        except IOError:
            print "Unable to open {0}, check your .timerc file or the rights on the timesheet" \
                .format(self.config['timesheet'])
            exit(1)

        re_sheet = re.compile(ur'(^[0-9- :]+)([ a-zA-Z]+)?(#[ \S]+$)?', re.MULTILINE)

        sheet_data = re.findall(re_sheet, sheet_data)

        date_start, date_end = date_range()

        for entry in sheet_data:
            entry_date = entry[0].split(':')[0]
            parsed_date = self.parse_date(entry_date)
            if date_start <= parsed_date <= date_end:
                self.filtered_entires.append(entry)

    def extra_actions(self):  # This is the part that manages printing and mailing users
        if self.args.e:

            if not "uio.no" in socket.getfqdn():
                print "Note: found something other than the uio.no domain, mail might not work"

            addr_to = self.args.e
            subject = '[Timescript] on behalf of ' + getpass.getuser()
            smtp = 'smtp.uio.no'
            atta = os.path.abspath(self.config['output name'])

            # Run the powershell mail command here
            print "Note, mail command might take some time"

            if 'nt' in os.name: #Windows systems
                args = shlex.split(
                    r'powershell.exe -NoProfile Send-MailMessage '
                    r'-To {0} -From {0} -Subject {1} -SmtpServer {2} -Attachments "{3}"'
                    .format(addr_to, subject, smtp, atta))

                try:
                    Popen(args=args, shell=True, stdin=PIPE, stdout=PIPE)
                except OSError:
                    print "Unable to find powershell... what on earth are you running?\nUse a UiO machine"


            elif 'posix' in os.name: #Nix systems
                args = shlex.split(r'mailx -a {0} -s "{1}" {2}'.format(atta,subject,addr_to))
                try:
                    Popen(args=args, shell=False, stdin=PIPE, stdout=PIPE)
                except OSError:
                    print "Unable to find the mailx command, this should only be used on a UiO machine due to filtering"

            else:
                print "No clue what the given OS is"

        if self.args.p:
            if 'nt' in os.name:
                exit(1)

            elif 'posix' in os.name:
                args = shlex.split(r'pushprint -P {0} {1}'.format(self.args.p,os.path.abspath(self.config['output name'])))
                try:
                    Popen(args=args, shell=False, stdin=PIPE, stdout=PIPE)
                except OSError:
                    print "Unable to find the pushprint command, are you one a UiO machine?"

            # TODO: Implement printing
            raise NotImplementedError("Printing not implemented")

    # noinspection PyPep8Naming
    def generate_PDF(self):
        pdf = PDF()
        pdf.add_page()

        pdf.set_font('Arial')
        pdf.multi_cell(w=200, h=8, txt="Name: {0}\nStilling: {1}\nPay grade: {2}\nPlace of work: {3}\nSSN: {4}"
                       .format(self.config['name'], self.config['position'], self.config['pay grade'],
                               self.config['place'],
                               self.config['pnr']), align='L', )

        pdf.ln(10)
        # Done creating info and top text

        # Starting to create cells
        # Creating the header row
        pdf.set_font('Arial', size=12)
        cell_height = 6
        time_size = 20
        note_size = 74
        sign_size = 30

        pdf.cell(25, cell_height * 2, txt="Date", border=1, ln=0, align='C')
        pdf.cell(20, cell_height * 2, txt="Week", border=1, ln=0, align='C')
        pdf.cell(time_size * 2, cell_height, txt="Time", border=1, ln=2, align='C')

        x, y = pdf.get_x(), pdf.get_y()

        pdf.cell(time_size, cell_height, txt="From", border=1, ln=0, align='C')
        pdf.cell(time_size, cell_height, txt="To", border=1, align='C')
        pdf.set_xy(x + time_size * 2, y - cell_height)
        pdf.cell(note_size, cell_height * 2, txt="Notes", border=1, ln=0, align='C')
        pdf.cell(sign_size, cell_height * 2, txt="Sign", border=1, ln=1, align='C')

        # Done creating top row
        pdf.set_font('Arial', size=12, style='b')

        for entry in self.filtered_entires:
            entry_date = entry[0].split(':')
            datetime_obj = self.parse_date(entry_date[0])
            datetime_str = datetime_obj.strftime('%Y-%m-%d')

            week_num = str(datetime_obj.isocalendar()[1])

            time_sum, time_from, time_to = self.get_hours(entry[0])

            if time_from is None and time_to is None:
                time_to = 'Hours'
                time_from = str(time_sum)
            else:
                time_from = time_from.strftime('%H:%M')
                time_to = time_to.strftime('%H:%M')

            self.sum_hour += time_sum

            note = str(entry[2])
            note = note[1:].decode('UTF-8')

            note_height = cell_height

            scalar = math.ceil(len(note) / 30.0)
            if scalar > 1:
                cell_height *= scalar

            pdf.cell(25, cell_height, txt=datetime_str, ln=0, border=1, align='C')  # Date cell
            pdf.cell(20, cell_height, txt=week_num, ln=0, border=1, align='C')  # Week number cell
            pdf.cell(time_size, cell_height, border=1, txt=time_from)  # From time
            pdf.cell(time_size, cell_height, border=1, txt=time_to)  # To time

            x, y = pdf.get_x(), pdf.get_y()

            pdf.multi_cell(note_size, note_height, border=1, txt=note)  # Notes
            pdf.set_xy(x + note_size, y)
            pdf.cell(sign_size, cell_height, border=1, ln=1)  # Sign

            if scalar > 1:
                cell_height /= scalar

        # After writing all the entries, we have an other entry as a note with the number of hours total

        pdf.cell(25, cell_height, ln=0, border=0, align='C')  # Date cell
        pdf.cell(20, cell_height, ln=0, border=0, align='C')  # Week number cell
        pdf.cell(time_size, cell_height, border=0, align='C')  # From time
        pdf.cell(time_size, cell_height, border=0, align='C')  # To time
        pdf.cell(note_size, cell_height, border=1, txt="Total hours: {0}".format(self.sum_hour))  # Notes
        pdf.cell(sign_size, cell_height, border=0, ln=1)

        file_name = datetime.now().strftime("%Y-%m-%d.pdf")

        if self.args.o:
            file_name = self.args.o

        pdf.output(file_name)

        self.config['output name'] = file_name

    def summation(self):
        hourly_rate = self.get_hourly_rate()
        tax_rate = self.config['tax percentage']
        tax = hourly_rate * self.sum_hour * tax_rate / 100
        income = hourly_rate * self.sum_hour - tax
        print summation.format(self.config['pay grade'], hourly_rate, self.sum_hour, hourly_rate * self.sum_hour,
                               tax_rate, tax, income)

    def __init__(self):
        self.config = {}
        self.args = None
        self.filtered_entires = []
        self.sum_hour = 0

        self.parse_commands()
        self.parse_config()
        self.parse_timesheet()
        self.generate_PDF()
        self.extra_actions()
        self.summation()


date_str_formats = ['%Y-%m-%d', '%y%m', '%y%m%d']
hour_str_formats = ['%H:%M', '%H']

summation = r'''
Pay grade                  {0}

Hourly rate:               {1}
Hours worked               {2}
---------------------------------
Pre-tax                    {3}
Taxation ({4})             {5}
=================================
Post-tax                   {6}
'''

timesheet_example = r'''
Example of timesheet content:
    YYYY-MM-DD: hh:mm-hh:mm # commentary
    YYMM: tt # Javakurs
    YYMMDD: hh-hh # Langfredag

'''

timerc_example = r'''
The following things should be in the .timerc file:
    name:           Namey McName
    tax percentage: 0                    # how much you are taxed
    pay grade:      0                    # what pay grade you got
    timesheet:      ~/timer.txt          # placement of your timesheet
    pnr:            12345123450          # leave blank if you do not wish this to be added
    position:       Guardian of Time     # name of your position
    place:          IFI                  # place of work'''

if __name__ == '__main__':
    penger = Penger()
