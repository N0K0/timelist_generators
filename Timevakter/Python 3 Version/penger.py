#!/usr/bin/env python
import argparse
import math
import os
import re
import shlex
import sys
from urllib import request
from datetime import datetime, timedelta
import calendar
from subprocess import Popen, PIPE
import getpass
import socket
import tempfile



from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5 import QtCore, QtGui, QtWidgets


sys.tracebacklimit = 10

try:
    from PyQt5 import QtCore
except ImportError as err:
    print('Unable to import PyQt5, please download the package')
    print('NOTE: On uio? You can use \'pip install --user fpdf\' '
          'to install without locally without the need of Sudo')
    raise err

try:
    from fpdf import FPDF
except ImportError as err:
    FPDF = None
    print('Unable to import fpdf, please download the package')
    print('NOTE: On uio? You can use \'pip install --user fpdf\' '
          'to install without locally without the need of Sudo')
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


# noinspection PyClassHasNoInit
class PDF(FPDF):
    def header(self):
        # Logo
        logo = request.urlopen(uio_logo_url).read()
        temp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
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

        connection = request.urlopen(pay_grade_table)
        content = connection.read().decode("utf-8")

        content = content.replace(',', '.')
        lines = content.split('\n')

        if grade < 19:
            print("Your pay grade is lower than what UiO generally allows... Somethings is wrong here")
            self.config['rate'] = 0
            return self.config['rate']

        if grade > 101:
            print("Dude, you are making too much money (pay grade stops at 101)")
            self.config['rate'] = 0
            return self.config['rate']

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
        parser.add_argument('-c', metavar='--config', type=str, default=".timerc",
                            help="Specify a config file. Use this if you for example got multiple jobs")
        parser.add_argument('-s', '--silent',action='store_true', default=False,
                            help="Used to generate the pdfs without the GUI")
        self.args = parser.parse_args()

    def parse_config(self):

        if not os.path.exists(self.args.c):
            print("NOTE: Was unable to find your time config file, so made a new one at {0}"
                  .format(os.path.abspath(self.args.c)))

            example = request.urlopen(timerc_example_url).read()
            config = open(self.args.c, 'w')
            config.write(example)
            config.close()

        try:
            config = open(self.args.c, 'r')
            config_str = config.read()

            re_config = re.compile('(.*?):\s+([_\\~./0-9a-zA-Z -]*)(#.*$|$)', re.MULTILINE)

            config_res = re.findall(re_config, config_str)

            for pair in config_res:
                self.config[pair[0]] = pair[1].strip()

            non_ta_set = {'name', 'timesheet', 'pnr', 'position', 'place', 'pay grade'}
            ta_set = {'name', 'subject code', 'timesheet', 'birth date'}

            non_ta_set = set(non_ta_set) - set(self.config.keys())
            ta_set = set(ta_set) - set(self.config.keys())

            if len(non_ta_set) == 0 and len(ta_set) == 0:
                print("[!] Unable to discern if this is a file for a TA or a non-TA config")
                print("[!] Note: TA does not need to list position")
                exit(1)

            if len(non_ta_set) == 0:
                self.config['extended'] = False
            elif len(ta_set) == 0:
                self.config['extended'] = True
                self.config['position'] = 'Teaching assistant'
            else:
                print("Error with the keys in the config file.")
                print(
                    "Has found: {0}\nMissing the key(s) for non-TA: {1}\nMissing the key(s) for TA: {2}\n"
                    .format(', '.join(self.config.keys()), ', '.join(non_ta_set), ', '.join(ta_set)))
                print(timerc_example)
                exit(1)

            self.config['tax percentage'] = float(self.config.setdefault('tax percentage', 0))
            self.config['pay grade'] = int(self.config.setdefault('pay grade', 0))
        except IOError:
            print("Unable to find a .timerc file, creating an example file for you")

    def parse_activity(self, activity_str, time_sum):
        activity_str = activity_str.strip().lower()
        if activity_str == '':
            self.hours['other'] = self.hours.setdefault('other', 0.0) + time_sum
            return 'other'
        if 'meet' in activity_str or 'meeting' in activity_str:
            self.hours['meeting'] = self.hours.get('meeting', 0.0) + time_sum
            return 'meeting'
        elif 'class preparation' in activity_str or 'cprep' in activity_str:
            self.hours['cprep'] = self.hours.get('cprep', 0.0) + time_sum
            return 'class preparation'
        elif 'lab preparation' in activity_str or 'lprep' in activity_str:
            self.hours['lprep'] = self.hours.get('lprep', 0.0) + time_sum
            return 'lab preparation'
        elif 'class' in activity_str:
            self.hours['class'] = self.hours.get('class', 0.0) + time_sum
            return 'class'
        elif 'lab' in activity_str:
            self.hours['lab'] = self.hours.get('lab', 0.0) + time_sum
            return 'lab'
        elif 'communication' in activity_str or 'com' in activity_str:
            self.hours['com'] = self.hours.get('com', 0.0) + time_sum
            return 'communication'
        elif 'oblig' in activity_str:
            oblig_lst = activity_str.split()
            # Index overview 0: Oblig name
            #               1: Oblig num
            #               2: Try number?
            #               3: Number of obligs
            # Saves the try num and Number of Obligs in a key named after the oblig num

            key = '{0}:{1}'.format(oblig_lst[1], oblig_lst[2])
            tmp = self.oblig.get(key, [0, 0])
            tmp[0] += int(oblig_lst[3])
            tmp[1] += time_sum

            self.oblig[key] = tmp  # Finally it will look like {'2:1': [20, 2L]}
            return 'oblig'

        else:
            self.hours['other'] = self.hours.setdefault('other', 0) + time_sum
            return 'other'

    @staticmethod
    def parse_date(date_str):
        date_str = date_str.strip()
        for date_format in date_str_formats:
            try:
                return datetime.strptime(date_str, date_format) + timedelta(seconds=1)
            except ValueError:
                pass
        return False

    @staticmethod
    def parse_hours(hour_str):
        hour_str = hour_str.strip()
        for hour_format in hour_str_formats:
            try:
                return datetime.strptime(hour_str, hour_format)
            except ValueError:
                pass

        return False

    def get_hours(self, hour_str):
        p = re.compile(':(.*)$', re.MULTILINE)

        time_res = re.search(p, hour_str)
        time_str_org = str(time_res.groups(0)[0]).strip()
        time_str = time_str_org.split('-')
        if len(time_str) == 1:
            time_from = None
            time_to = None
            hour_sum = float(time_str[0])
        else:
            time_from, time_to = self.parse_hours(time_str[0]), self.parse_hours(time_str[1])

            if time_from is False or time_to is False:
                print("Error parsing the following time range: '{0}'".format(time_str_org))
                exit(1)

            time_delta = time_to - time_from
            # Using this horrible shit of an formula since UiO has an outdated timedate (total_sec is not implemented)
            hour_sum = time_delta.days * 24.0 + time_delta.seconds / 3600.0

        return hour_sum, time_from, time_to

    def parse_timesheet(self):

        # http://stackoverflow.com/questions/42950/get-last-day-of-the-month-in-python
        date_today = datetime.today()

        # noinspection PyShadowingNames
        def date_range():
            if self.args.y and self.args.m:
                date_start = datetime(self.args.y, self.args.m, 1)

                end_day = calendar.monthrange(self.args.y, self.args.m)[1]
                date_end = datetime(self.args.y, self.args.m, 1)
                date_end = date_end + timedelta(days=end_day) - timedelta(seconds=1)
            elif self.args.m:
                date_start = datetime(date_today.year, self.args.m, 1)

                end_day = calendar.monthrange(date_today.year, self.args.m)[1]
                date_end = datetime(date_start.year, self.args.m + 1, 1)
                date_end = date_end + timedelta(days=end_day) - timedelta(seconds=1)
            elif self.args.y:
                date_start = datetime(self.args.y, 1, 1)
                end_day = calendar.monthrange(self.args.y, date_today.month)[1]

                date_end = datetime(self.args.y + 1, 1, 1)
                date_end = date_end + timedelta(days=end_day) - timedelta(seconds=1)
            else:
                date_start = datetime(date_today.year, date_today.month, 1)

                end_day = calendar.monthrange(date_today.year, date_today.month)[1]
                date_end = datetime(date_today.year, date_today.month + 1, 1)
                date_end = date_end + timedelta(days=end_day) - timedelta(seconds=1)

            self.config['month name'] = date_start.strftime('%B - %Y')
            return date_start, date_end

        sheet_data = ''
        try:
            path = os.path.expanduser(self.config['timesheet'])
            sheet = open(path, 'r')
            sheet_data = sheet.read()
        except IOError:
            print("Unable to open {0}, check your .timerc file or the rights on the timesheet"
                  .format(self.config['timesheet']))
            exit(1)

        re_sheet = re.compile('(^[0-9- :.,]+)([ a-zA-Z0-9:]+)?(#[ \S]*$)?', re.MULTILINE)

        sheet_data = re.findall(re_sheet, sheet_data)

        date_start, date_end = date_range()

        for entry in sheet_data:
            entry_date = entry[0].split(':')[0]
            parsed_date = self.parse_date(entry_date)

            if parsed_date is False:
                print(r"Error parsing the following date: {0}\nCheck your timesheet".format(entry))
                exit(1)

            if date_start <= parsed_date <= date_end:
                self.filtered_entries.append(entry)

    def extra_actions(self):  # This is the part that manages printing and mailing users
        if self.args.e:

            if "uio.no" not in socket.getfqdn():
                print("Note: found something other than the uio.no domain, mail might not work")

            address_to = self.args.e
            attachment = os.path.abspath(self.config['output name'])
            subject = '[Timescript] {0} on behalf of {1}'.format(self.config['output name'], getpass.getuser())
            smtp = 'smtp.uio.no'

            # Run the powershell mail command here
            print("Note, mail command might take some time")

            if 'nt' in os.name:  # Windows systems
                args = shlex.split(
                    r'powershell.exe -NoProfile Send-MailMessage '
                    r'-To {0} -From {0} -Subject {1} -SmtpServer {2} -Attachments "{3}"'.format(
                        address_to, subject, smtp, attachment))

                try:
                    Popen(args=args, shell=True, stdin=PIPE, stdout=PIPE)
                except OSError:
                    print("Unable to find powershell... what on earth are you running?\nUse a UiO machine")

            elif 'posix' in os.name:  # Unix systems
                args = shlex.split(r'mailx -a {0} -s "{1}" {2}'.format(attachment, subject, address_to))
                try:
                    Popen(args=args, shell=False, stdin=PIPE, stdout=PIPE)
                except OSError:
                    print(
                        "Unable to find the mailx command, this should only be used on a UiO machine due to filtering")

            else:
                print("No clue what the given OS is")

        if self.args.p:
            if 'nt' in os.name:
                # There got to be a cleaner way to do this :C
                print("Note, might take some time to setup the printer you want")
                args = shlex.split(
                    r'powershell.exe (New-Object -ComObject WScript.Network).AddWindowsPrinterConnection("\\pushprint.uio.no\{0}")'
                    .format(self.args.p), posix=False)
                shell = Popen(args=args, shell=True, stdin=PIPE, stdout=PIPE)
                print(shell.communicate())
                args = shlex.split(
                    r'powershell.exe (New-Object -ComObject WScript.Network).SetDefaultPrinter("\\pushprint.uio.no\{0}")'
                    .format(self.args.p), posix=False)
                shell = Popen(args=args, shell=True, stdin=PIPE, stdout=PIPE)
                print(shell.communicate())
                args = shlex.split(r'powershell.exe Start-Process -FilePath {0} -Verb Print'.format(
                    os.path.abspath(self.config['output name'])), posix=False)
                print(args)
                shell = Popen(args=args, shell=True, stdin=PIPE, stdout=PIPE)
                print(shell.communicate())

            elif 'posix' in os.name:
                args = shlex.split(
                    r'pushprint -P {0} {1}'.format(self.args.p, os.path.abspath(self.config['output name'])))
                try:
                    Popen(args=args, shell=False, stdin=PIPE, stdout=PIPE)
                except OSError:
                    print("Unable to find the pushprint command, are you on a UiO machine?")

    # noinspection PyPep8Naming
    def generate_PDF(self):
        pdf = PDF()
        pdf.add_page()

        pdf.set_font('Arial')

        if self.config['extended']:
            pdf.multi_cell(w=200, h=8, txt="Name: {0}\nPosition: {1}\n"
                           .format(self.config['name'], self.config['position'], align='L'))
        else:
            pdf.multi_cell(w=200, h=8, txt="Name: {0}\nPosition: {1}\nPay grade: {2}\nPlace of work: {3}\nSSN: {4}"
                           .format(self.config['name'], self.config['position'], self.config['pay grade'],
                                   self.config['place'],
                                   self.config['pnr']), align='L')

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

        # Actually figuring out how many hours and such here
        for entry in self.filtered_entries:
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

            note = str(entry[2])
            note = note[1:].strip()

            if self.config.get('extended') is True:
                ret = self.parse_activity(entry[1], time_sum)
                note += '({0})'.format(ret)

            note = note.strip()
            self.sum_hour += time_sum

            note_height = cell_height

            scalar = math.ceil(len(note) / 24.0)
            if scalar > 1:
                cell_height *= scalar

            pdf.cell(25, cell_height, txt=datetime_str, ln=0, border=1, align='C')  # Date cell
            pdf.cell(20, cell_height, txt=week_num, ln=0, border=1, align='C')  # Week number cell
            pdf.cell(time_size, cell_height, border=1, txt=time_from)  # From time
            pdf.cell(time_size, cell_height, border=1, txt=time_to)  # To time

            x, y = pdf.get_x(), pdf.get_y()

            pdf.set_font('Courier', size=12, style='b')
            pdf.multi_cell(note_size, note_height, border=1, txt=note, align='c')  # Notes
            pdf.set_font('Arial', size=12, style='b')

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

        if self.config.get('extended') is True:
            pdf = self.TA_page(pdf)

        if self.args.o:
            file_name = self.args.o

        try:
            pdf.output(file_name)
        except IOError as e:
            print("Could not write to {0}".format(file_name))
            print("Is the PDF open in a reader?")
            exit(1)

        self.config['output name'] = file_name

    # noinspection PyPep8Naming
    def TA_page(self, pdf):
        pdf.set_font('Arial', size=12)

        first_name, last_name = self.config['name'].rsplit(' ', 1)
        birth_date = self.config['birth date']

        pdf.add_page()
        page_width = pdf.w - pdf.l_margin - pdf.r_margin  # Size of actual page area
        # Information about the TA
        info_width = page_width / 3
        info_height = 15

        # 1st line
        pdf.set_font('Arial', size=8)
        x, y = pdf.get_x(), pdf.get_y()
        pdf.cell(info_width, 5, txt='First Name')
        pdf.cell(info_width, 5, txt='Subject Code')
        pdf.cell(info_width, 5, txt='Date of Birth')
        pdf.set_xy(x, y)

        pdf.set_font('Arial', size=14, style='B')
        pdf.cell(info_width, info_height, align='C', border=1, txt=first_name)
        pdf.cell(info_width, info_height, align='C', border=1, txt=self.config['subject code'])
        pdf.cell(info_width, info_height, align='C', border=1, txt=birth_date, ln=1)

        # 2nd line
        pdf.set_font('Arial', size=8)
        x, y = pdf.get_x(), pdf.get_y()
        pdf.cell(info_width, 5, txt='Last Name')
        pdf.cell(info_width, 5, txt='Month')
        pdf.cell(info_width, 5, txt='Total number of hours')
        pdf.set_xy(x, y)

        pdf.set_font('Arial', size=14, style='B')
        pdf.cell(info_width, info_height, align='C', border=1, txt=last_name)
        pdf.cell(info_width, info_height, align='C', border=1, txt=self.config['month name'])
        pdf.cell(info_width, info_height, align='C', border=1, txt=str(self.sum_hour), ln=1)
        pdf.ln(10)

        # Done with 2nd Line

        # Specification of the hours

        pdf.cell(pdf.w / 2, info_height / 2, txt='Specification of hours', ln=1)
        pdf.set_font('Arial', size=14)
        pdf.cell(pdf.w, info_height / 2, txt='(Class of lecturing = 2 hours, or rounded to nearest quarter hour)',
                 ln=1)
        pdf.set_font('Arial', size=14, style='B')

        hour_h = 12
        hour_w = page_width / 2

        pdf.cell(hour_w, hour_h / 2, txt="Activity", border=1)
        pdf.cell(hour_w, hour_h / 2, txt="Number of hours", border=1, ln=1)

        pdf.cell(hour_w, hour_h, border=1, txt='Meeting')
        pdf.cell(hour_w, hour_h, border=1, ln=1, txt=str(self.hours.get('meeting', 0)))

        pdf.cell(hour_w, hour_h, border=1, txt='Preparation for lab')
        pdf.cell(hour_w, hour_h, border=1, ln=1, txt=str(self.hours.get('lprep', 0)))

        pdf.cell(hour_w, hour_h, border=1, txt='Lab')
        pdf.cell(hour_w, hour_h, border=1, ln=1, txt=str(self.hours.get('lab', 0)))

        pdf.cell(hour_w, hour_h, border=1, txt='Preparation for Class')
        pdf.cell(hour_w, hour_h, border=1, ln=1, txt=str(self.hours.get('cprep', 0)))

        pdf.cell(hour_w, hour_h, border=1, txt='Class')
        pdf.cell(hour_w, hour_h, border=1, ln=1, txt=str(self.hours.get('class', 0)))

        pdf.cell(hour_w, hour_h, border=1, txt='Communication outside class')
        pdf.cell(hour_w, hour_h, border=1, ln=1, txt=str(self.hours.get('com', 0)))

        pdf.cell(hour_w, hour_h, border=1, txt='Other (See work log for reference)')
        pdf.cell(hour_w, hour_h, border=1, ln=1, txt=str(self.hours.get('other', 0)))

        pdf.ln(10)

        # Specification for the oblig's

        oblig_w = page_width / 4
        oblig_h = hour_h

        pdf.cell(oblig_w, oblig_h / 2, border=1, txt="Oblig number")
        pdf.cell(oblig_w, oblig_h / 2, border=1, txt="Try number")
        pdf.cell(oblig_w, oblig_h / 2, border=1, txt="Number of obligs")
        pdf.cell(oblig_w, oblig_h / 2, border=1, txt="Sum hours", ln=1)

        for entry in self.oblig:
            oblig_num, try_num = entry.split(':', 1)
            corrected, hours = self.oblig.get(entry, (0, 0))

            pdf.cell(oblig_w, oblig_h, border=1, txt=str(oblig_num))
            pdf.cell(oblig_w, oblig_h, border=1, txt=str(try_num))
            pdf.cell(oblig_w, oblig_h, border=1, txt=str(corrected))
            pdf.cell(oblig_w, oblig_h, border=1, txt=str(hours), ln=1)

        pdf.ln(10)

        # Done with oblig spec

        # Adding signature field

        sign_w = page_width / 8
        sign_h = oblig_h

        pdf.set_font('Arial', size=8)
        x, y = pdf.get_x(), pdf.get_y()
        pdf.cell(sign_w, 5, txt='Date')
        pdf.cell(sign_w * 3.5, 5, txt='Student')
        pdf.cell(sign_w * 3.5, 5, txt='Course administrator')
        pdf.set_xy(x, y)

        pdf.set_font('Arial', size=14, style='B')
        pdf.cell(sign_w, sign_h, align='C', border=1, txt='')
        pdf.cell(sign_w * 3.5, sign_h, align='C', border=1, txt='')
        pdf.cell(sign_w * 3.5, sign_h, align='C', border=1, txt='')

        return pdf

    def summation(self):
        hourly_rate = self.get_hourly_rate()
        tax_rate = self.config['tax percentage']
        tax = hourly_rate * self.sum_hour * tax_rate / 100
        income = hourly_rate * self.sum_hour - tax
        print(summation.format(self.config['pay grade'], hourly_rate, self.sum_hour, hourly_rate * self.sum_hour,
                               tax_rate, tax, income))

    def __init__(self):
        self.config = {}
        self.hours = {}
        self.oblig = {}
        self.args = None
        self.filtered_entries = []
        self.sum_hour = 0
        self.parse_commands()
        self.parse_config()
        self.parse_timesheet()

        if self.args.silent:
            self.generate_PDF()
            self.extra_actions()
            self.summation()


date_str_formats = ['%Y-%m-%d', '%y%m', '%y%m%d']
hour_str_formats = [r'%H:%M', r'%H']

summation = r'''
Pay grade                  {0}

Hourly rate:               {1:.1f}
Hours worked               {2:.2f}
---------------------------------
Pre-tax                    {3:.1f}
Taxation ({4})             {5:.1f}
=================================
Post-tax                   {6:.1f}
'''

timesheet_example = r'''
Formatting of timesheet content for non teaching assistants:
    YYYY-MM-DD: hh:mm-hh:mm # commentary
    YYMM: tt # Comment
    YYMMDD: hh-hh

Formatting of timesheet content for teaching assistants:
NOTE: All the formatting from above works. The only field that is really different is the usage of a "activity"
    part of a entry:
        YYYY-MM-DD: tt _ACTIVITY GOES HERE_ # Commentary

    Example
        YYYY-MM-DD: hh:mm-hh:mm meeting # Commentary
        YYMM: tt Cprep # Commentary

    Meeting:
        Name: meeting (meet)
    Preparation for class:
        Name: Class preparation (Cprep)
    Preparation for lab:
        Name: Lab preparation (Lprep)
    Class:
        Name: Class (Class)
    Lab:
        Name: Lab (Lab)
    Out of class communication with students:
        Name: communication (com)
    Oblig (oblig):
        This is a special case that requires some more arguments int the form of the following

         0: Oblig name
         1: Oblig num
         2: Try number?
         3: Number of obligs

         So the line looks something like:
            YYYY-MM-DD: HH oblig oblig_number try_number number_of_obligs #Comment
            2016-09-22: 8 oblig 1 1 8 #Obligger

'''

timerc_example = r'''
The following things is needed be in the .timerc for non teaching assistants:
    name:           Name McName
    timesheet:      ~/timer.txt          # placement of your timesheet
    pnr:            12345123450          # leave blank if you do not wish this to be added
    position:       Guardian of Time     # name of your position
    place:          IFI                  # place of work

The following things is needed be in the .timerc for teaching assistants:
    name:           Name McName
    subject code:   INF2100              # Subject code
    timesheet:      ~/timer.txt          # placement of your timesheet

Optional arguments for both:
    tax percentage: 0                    # how much you are taxed
    pay grade:      0                    # what pay grade you got
'''


class ManagerGui(QMainWindow):
    # http://zetcode.com/gui/pyqt5
    # Guide

    def time_sheet_selector(self):
        file_path = QFileDialog(self).getOpenFileName()
        print(file_path)
        return file_path

    def time_sheet_selector(self):
        file_path = QFileDialog(self).getOpenFileName()
        print(file_path)
        return file_path

    def __init__(self,penger):
        self.penger = penger
        super().__init__()
        self.init_ui(self)

    def init_ui(self, MainWindow):
        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(800, 600)
        self.centralwidget = QtWidgets.QWidget(MainWindow)
        self.centralwidget.setObjectName("centralwidget")
        self.treeWidget = QtWidgets.QTreeWidget(self.centralwidget)
        self.treeWidget.setEnabled(True)
        self.treeWidget.setGeometry(QtCore.QRect(0, 0, 791, 571))
        self.treeWidget.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.treeWidget.setSizeAdjustPolicy(QtWidgets.QAbstractScrollArea.AdjustToContents)
        self.treeWidget.setColumnCount(4)
        self.treeWidget.setObjectName("treeWidget")
        self.treeWidget.header().setHighlightSections(True)
        self.treeWidget.header().setMinimumSectionSize(37)
        self.treeWidget.header().setSortIndicatorShown(False)
        MainWindow.setCentralWidget(self.centralwidget)
        self.toolBar = QtWidgets.QToolBar(MainWindow)
        self.toolBar.setAllowedAreas(QtCore.Qt.NoToolBarArea)
        self.toolBar.setFloatable(False)
        self.toolBar.setObjectName("toolBar")
        MainWindow.addToolBar(QtCore.Qt.TopToolBarArea, self.toolBar)
        self.action_file_open_sheet = QtWidgets.QAction(MainWindow)
        self.action_file_open_sheet.setObjectName("action_file_open_sheet")
        self.action_file_open_config = QtWidgets.QAction(MainWindow)
        self.action_file_open_config.setObjectName("action_file_open_config")
        self.action_exit = QtWidgets.QAction(MainWindow)
        self.action_exit.setObjectName("action_exit")
        self.action_generate_PDF = QtWidgets.QAction(MainWindow)
        self.action_generate_PDF.setObjectName("action_generate_PDF")
        self.toolBar.addAction(self.action_file_open_sheet)
        self.toolBar.addAction(self.action_file_open_config)
        self.toolBar.addAction(self.action_generate_PDF)
        self.toolBar.addAction(self.action_exit)

        self.retranslateUi(MainWindow)
        self.action_exit.triggered.connect(MainWindow.close)
        QtCore.QMetaObject.connectSlotsByName(MainWindow)

    def retranslateUi(self, MainWindow):
        _translate = QtCore.QCoreApplication.translate
        MainWindow.setWindowTitle(_translate("MainWindow", "Time sheet generator -- Nikolasp"))
        self.treeWidget.headerItem().setText(0, _translate("MainWindow", "Date"))
        self.treeWidget.headerItem().setText(1, _translate("MainWindow", "Time"))
        self.treeWidget.headerItem().setText(2, _translate("MainWindow", "Category"))
        self.treeWidget.headerItem().setText(3, _translate("MainWindow", "Comment"))
        self.toolBar.setWindowTitle(_translate("MainWindow", "toolBar"))
        self.action_file_open_sheet.setText(_translate("MainWindow", "Open sheet"))
        self.action_file_open_sheet.setToolTip(_translate("MainWindow", "Open the time sheet"))
        self.action_file_open_sheet.setShortcut(_translate("MainWindow", "Ctrl+O"))
        self.action_file_open_config.setText(_translate("MainWindow", "Open config"))
        self.action_file_open_config.setToolTip(_translate("MainWindow", "Open the config file"))
        self.action_file_open_config.setShortcut(_translate("MainWindow", "Ctrl+C"))
        self.action_exit.setText(_translate("MainWindow", "Exit"))
        self.action_exit.setShortcut(_translate("MainWindow", "Ctrl+Q"))
        self.action_generate_PDF.setText(_translate("MainWindow", "Generate PDF"))
        self.action_generate_PDF.setToolTip(_translate("MainWindow", "Push to save the pdf"))
        self.action_generate_PDF.setShortcut(_translate("MainWindow", "Ctrl+S"))

        # Finalizing
        self.show()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    penger = Penger()

    if penger.args.silent:
        exit(0)

    gui = ManagerGui(penger)
    sys.exit(app.exec_())
