from enum import Enum
from xlrd import open_workbook

class DeviceType(Enum):
    big = 1
    little = 2
    gpu = 3

class EnergyValue:

    def __init__(self, device, frequency, correlation, alpha, beta):
        self.device = device
        self.frequency = frequency
        self.correlation = correlation
        self.alpha = alpha
        self.beta = beta

class EnergyProfile:

    def __init__(self):
        self.little_values = []
        self.big_values = []
        self.gpu_values = []
        self.get_data()

    def parse_row(self, sheet, device, row):
        freq = int(sheet.cell(row, 0).value)
        correlation = sheet.cell(row, 1).value
        alpha = sheet.cell(row, 2).value
        beta = sheet.cell(row,3).value

        return EnergyValue(device, freq, correlation, alpha, beta)

    def get_data(self):

        wb = open_workbook('constants.xls')
        sheet = wb.sheets()[0]

        #big data
        for row in range(1,10):
            self.big_values.append(self.parse_row(sheet, DeviceType.big, row))

        #little data
        for row in range(12, 17):
            self.little_values.append(self.parse_row(sheet, DeviceType.little, row))

        #gpu data
        for row in range(19, 25):
            self.gpu_values.append(self.parse_row(sheet, DeviceType.gpu, row))
