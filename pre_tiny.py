import redpctl as redpctl
import time
import numpy as np

from LTC1380 import LTC1380
from DAT31R5A import Attenuator
from LTC6912 import LTC6912

import signal_helper as sh
import pandas as pd

pd.options.display.max_columns = None


class PRE_TESTs:
    def __init__(self, bus):
        self.bus = bus
        self.MUX = LTC1380(self.bus)
        self.ATT = Attenuator(self.bus)
        self.AMP = LTC6912(self.bus)
        self.att_loss = 5.
        self.ATT.set_loss(int(self.att_loss))

        self.bus.pre_on(0)
        self.current = None
        self.counter = None
        self.last = None
        self.error = 0
        self.result = ""
        self.s = "_"
        self.data = []

        self.id_f = [26000., 60000., 150000.]
        self.brd = ["18", "40", "HS"]
        self.current_brd = None
        self.rms90 = 0

        self.ampl = 0.07
        self.vin = ((self.ampl / np.sqrt(2))/ sh.db_ratio(40))/sh.db_ratio(self.att_loss)

        self.TEST_all = [
            "BRD_ID",
            "MAIN_NOISE",
            "MAIN_GAIN_60",
            "MAIN_GAIN_LOW",
            "MAIN_BW",
            "LIM_NOISE",
            "LIM_BW",
        ]
        self.TEST_name = []

        self.df = pd.DataFrame(columns=self.TEST_all)
        # self.df.to_csv(
        #     "dataset/preamp_tiny.csv", mode="a", encoding="utf-8", index=False
        # )


        for i, text in enumerate(self.TEST_all):
            self.TEST_name.append(text)
        
        self.TEST_result = {
            "BRD_ID": ["<", 0.300],
            "MAIN_NOISE": [">", 0.250],
            "MAIN_GAIN_60": ["+-", 3.0, 60],
            "MAIN_GAIN_LOW": ["+-", 1.5, 42],
            "MAIN_BW": ["+-", 1.0, 60, 6, 6],
            "LIM_NOISE": [">", 0.350],
            "LIM_BW": ["+-", 1.0, 62, 6, 6],
        }

        self.BRD_setting = {
        #    Noise Gain  lowcut Gain db -6db -6db mid lim -3bd -3db
            "18": [0x66,  80000., 0x26, 11600., 52200., 26000.,5300., 67900.],  # BW Gain Low  11800.0 53800.0
            "40": [0x66, 130000., 0x26, 26800.,103500., 60000.,12700.,143300.], # BW Gain Low  27700.0 113100.0
            "HS": [0x55, 300000., 0x26, 58800.,209500.,150000.,30100.,335100.], # BW Gain Low  67300.0 218200.0
        }
    def test(self, brd=None):
        if self.current == None:
            self.counter = 0
            self.current = self.TEST_name[self.counter]
        else:
            self.counter = (self.counter + 1) % len(self.TEST_name)
            self.current = self.TEST_name[self.counter]

        if self.counter == len(self.TEST_name) - 1:
            self.last = 1

        if self.current == "BRD_ID":
            self.result = self.brd_id()
        
        elif self.current == "MAIN_NOISE":
            self.MUX.set_ch("ES_MAIN")
            self.result = self.brd_noise()


        elif self.current == "MAIN_GAIN_90":
            self.result = self.brd_db()
        
        elif self.current == "MAIN_GAIN_LOW":
            self.result = self.brd_gl()
        
        elif self.current == "MAIN_BW":
            self.result = self.brd_bw()

        elif self.current == "LIM_NOISE":
            self.MUX.set_ch("ES_LIM")
            self.result = self.brd_noise()
        
        elif self.current == "LIM_BW":
            self.MUX.set_ch("ES_LIM")
            self.result = self.lim_bw()

        return self.result
    
    def brd_id(self):
        self.MUX.set_ch("ES_MAIN")
        time.sleep(0.1) 
        self.bus.gen_on(1)
        self.bus.adc1_2(1)
        self.bus.ss_gl(0)
        self.bus.pre_on(1)
        self.AMP.send_8bit_int(0x66)
        brd_rms = []
        for i in self.id_f:
            self.bus.set_gen(wave_form="sine", freq=i, ampl=self.ampl)
            data = self.AMP.read_same_level(thresh = 0.1)
            brd_rms.append(round(sh.rms(data), 3))
        result= np.max(brd_rms)
        self.error = self.check_result(result)
        self.current_brd = self.brd[np.argmax(brd_rms)]
        self.df.loc[0, [self.current]] = [self.current_brd]
        return print(self.current_brd)
    
    def brd_noise(self):
        self.bus.gen_on(0)
        self.bus.ss_gl(1)
        self.AMP.send_8bit_int(self.BRD_setting[self.current_brd][0])
        time.sleep(0.5)
        # data = self.bus.read_oneL0()
        data = self.AMP.read_same_level(thresh = 0.05, slice = 100)
        y = sh.butter_lowpass_filter(
                    data, self.BRD_setting[self.current_brd][1], self.bus.fs, order=5)
        data = sh.voltage_divider_pre(y)
        result = sh.rms(data)
        self.error = self.check_result(result)
        self.df.loc[0, [self.current]] = [result]
        return self.print_tests(result)

    def brd_db(self):
        self.bus.set_gen(wave_form="sine", freq=self.BRD_setting[self.current_brd][5], ampl=self.ampl)
        self.bus.gen_on(1)
        self.bus.ss_gl(0)
        self.AMP.send_8bit_int(self.BRD_setting[self.current_brd][2])
        time.sleep(0.5)
        data = self.AMP.read_same_level(thresh = 0.05, slice = 100)
        result = sh.rms(data)
        self.rms90 = result
        result = sh.ratio_db(result, self.vin)
        self.error = self.check_result(result)
        self.df.loc[0, [self.current]] = [result]
        return self.print_tests(result)
    
    def brd_gl(self):
        self.bus.set_gen(wave_form="sine", freq=self.BRD_setting[self.current_brd][5], ampl=self.ampl)
        self.bus.gen_on(1)
        self.bus.ss_gl(1)
        self.AMP.send_8bit_int(self.BRD_setting[self.current_brd][2])
        time.sleep(0.5)
        data = self.AMP.read_same_level(thresh = 0.05, slice = 100)
        result = self.rms90 - sh.rms(data)
        self.error = self.check_result(result)
        self.df.loc[0, [self.current]] = [result]
        return self.print_tests(result)
    
    def brd_bw(self):
        result = []
        for i in (5,3,4):
            self.bus.set_gen(wave_form="sine", freq=self.BRD_setting[self.current_brd][i], ampl=self.ampl)
            time.sleep(0.2)
            self.bus.gen_on(1)
            self.bus.ss_gl(0)
            self.AMP.send_8bit_int(self.BRD_setting[self.current_brd][2])
            time.sleep(0.2)
            data = self.AMP.read_same_level(thresh = 0.05, slice = 100)
            if result == []:
                result.append(sh.ratio_db(sh.rms(data), self.vin))
            else:
                result.append(result[0] - sh.ratio_db(sh.rms(data), self.vin))
        self.error = self.check_result(result)
        self.df.loc[0, [self.current]] = [result]
        return self.print_tests(result)

    def lim_bw(self):
        self.ampl = 0.07
        self.vin = ((self.ampl / np.sqrt(2))/ sh.db_ratio(40))/sh.db_ratio(self.att_loss)
        result = []
        for i in (5,6,7):
            self.bus.set_gen(wave_form="sine", freq=self.BRD_setting[self.current_brd][i], ampl=self.ampl)
            self.bus.gen_on(1)
            time.sleep(0.5)
            self.bus.ss_gl(0)
            data = self.AMP.read_same_level(thresh = 0.05, slice = 100)
            if result == []:
                result.append(sh.ratio_db(sh.rms(data), self.vin))
            else:
                result.append(result[0] - sh.ratio_db(sh.rms(data), self.vin))
        self.error = self.check_result(result)
        self.df.loc[0, [self.current]] = [result]
        return self.print_tests(result)
    
    def check_result(self, result):
        self.error = False
        if self.TEST_result[self.current][0] == ">":
            if abs(result) > self.TEST_result[self.current][1]:
                self.error = True

        if self.TEST_result[self.current][0] == "<":
            if abs(result) < self.TEST_result[self.current][1]:
                self.error = True

        if self.TEST_result[self.current][0] == "%":
            if len(self.TEST_result[self.current]) == 3:
                if (
                    sh.percentage_change(abs(result), self.TEST_result[self.current][2])
                    > self.TEST_result[self.current][1]
                ):
                    self.error = True
            if len(self.TEST_result[self.current]) == 5:
                for count, value in enumerate(result):
                    if (
                        sh.percentage_change(
                            abs(value), self.TEST_result[self.current][count + 2]
                        )
                        > self.TEST_result[self.current][1]
                    ):
                        self.error = True

        if self.TEST_result[self.current][0] == "+-":
            if len(self.TEST_result[self.current]) == 3:
                self.error = sh.checking_width(
                    self.TEST_result[self.current][1],
                    self.TEST_result[self.current][2],
                    abs(result),
                )
            if len(self.TEST_result[self.current]) == 5:
                for count, value in enumerate(result):
                    self.error = sh.checking_width(
                        self.TEST_result[self.current][1],
                        self.TEST_result[self.current][count + 2],
                        abs(value),
                    )

        return self.error
    
    def print_tests(self, i=180.0):
        colors = {
            "cR": "\033[91m",
            "cG": "\033[92m",
            "cB": "\33[94m",
            "END": "\033[0m",
            "cX": 0,
        }
        result_str = ""
        colors["cX"] = colors["cR"] if self.error else colors["cG"]
        good = ("{cX}" + ("BAD" if self.error else "OK") + "{END}").format(**colors)

        if type(i) == list:
            result_str = " ".join(str(format(x, ".3f")) for x in i)
        else:
            result_str = str(format(i, ".3f"))
        print(f"{self.current:<18}", f"{result_str:<24}", f"{good}")
        return result_str
    
    def save_log(self):
        self.df.to_csv(
            "dataset/preamp_tiny.csv", mode="a", header=False, encoding="utf-8", index=False
        )



if __name__ == "__main__":
    import redpctl as redpctl
    import time, sys

    dec = 32
    rp_c = redpctl.RedCtl(dec=dec)
    T = PRE_TESTs(rp_c)

    for i in range(32):
        result = T.test()
        if T.error:
            print("error")
            break
        if T.last:
            break

    # rp_c.pre_on(0)
    # T.save_log()