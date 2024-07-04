"""Module: barcode.codex

:Provided barcodes: Code 39, Code 128, PZN
"""
from __future__ import annotations

from typing import Collection

from barcode.base import Barcode
from barcode.charsets import code39
from barcode.charsets import code128
from barcode.errors import BarcodeError
from barcode.errors import IllegalCharacterError
from barcode.errors import NumberOfDigitsError

__docformat__ = "restructuredtext en"

# Sizes
MIN_SIZE = 0.2
MIN_QUIET_ZONE = 2.54


def check_code(code: str, name: str, allowed: Collection[str]) -> None:
    wrong = []
    for char in code:
        if char not in allowed:
            wrong.append(char)
    if wrong:
        raise IllegalCharacterError(
            "The following characters are not valid for {name}: {wrong}".format(
                name=name, wrong=", ".join(wrong)
            )
        )


class Code39(Barcode):
    """A Code39 barcode implementation"""

    name = "Code 39"

    def __init__(self, code: str, writer=None, add_checksum: bool = True) -> None:
        r"""
        :param code: Code 39 string without \* and without checksum.
        :param writer: A ``barcode.writer`` instance used to render the barcode
            (default: SVGWriter).
        :param add_checksum: Add the checksum to code or not
        """

        self.code = code.upper()
        if add_checksum:
            self.code += self.calculate_checksum()
        self.writer = writer or self.default_writer()
        check_code(self.code, self.name, code39.REF)

    def __str__(self) -> str:
        return self.code

    def get_fullcode(self) -> str:
        """:returns: The full code as it will be encoded."""
        return self.code

    def calculate_checksum(self):
        check = sum(code39.MAP[x][0] for x in self.code) % 43
        for k, v in code39.MAP.items():
            if check == v[0]:
                return k
        return None

    def build(self):
        chars = [code39.EDGE]
        for char in self.code:
            chars.append(code39.MAP[char][1])
        chars.append(code39.EDGE)
        return [code39.MIDDLE.join(chars)]

    def render(self, writer_options=None, text=None):
        options = {"module_width": MIN_SIZE, "quiet_zone": MIN_QUIET_ZONE}
        options.update(writer_options or {})
        return super().render(options, text)


class PZN7(Code39):
    """Initializes new German number for pharmaceutical products.

    :parameters:
        pzn : String
            Code to render.
        writer : barcode.writer Instance
            The writer to render the barcode (default: SVGWriter).
    """

    name = "Pharmazentralnummer"

    digits = 6

    def __init__(self, pzn, writer=None) -> None:
        pzn = pzn[: self.digits]
        if not pzn.isdigit():
            raise IllegalCharacterError("PZN can only contain numbers.")
        if len(pzn) != self.digits:
            raise NumberOfDigitsError(
                f"PZN must have {self.digits} digits, not {len(pzn)}."
            )
        self.pzn = pzn
        self.pzn = f"{pzn}{self.calculate_checksum()}"
        super().__init__(f"PZN-{self.pzn}", writer, add_checksum=False)

    def get_fullcode(self):
        return f"PZN-{self.pzn}"

    def calculate_checksum(self):
        sum_ = sum(int(x) * int(y) for x, y in enumerate(self.pzn, start=2))
        checksum = sum_ % 11
        if checksum == 10:
            raise BarcodeError("Checksum can not be 10 for PZN.")

        return checksum


class PZN8(PZN7):
    """Will be fully added in v0.9."""

    digits = 7


class Code128(Barcode):
    """Initializes a new Code128 instance. The checksum is added automatically
    when building the bars.

    :parameters:
        code : String
            Code 128 string without checksum (added automatically).
        writer : barcode.writer Instance
            The writer to render the barcode (default: SVGWriter).
    """

    name = "Code 128"

    def __init__(self, code, writer=None) -> None:
        self.code = code
        self.writer = writer or self.default_writer()
        self._charset = self._guess_charset(code)
        self._buffer = ""
        check_code(self.code, self.name, code128.ALL)

    def __str__(self) -> str:
        return self.code

    @staticmethod
    def _guess_charset(code):
        if all(a.isdigit() for a in code):
            return 'C'
        return 'B'

    @property
    def encoded(self):
        return self._build()

    def get_fullcode(self):
        return self.code

    def _new_charset(self, which):
        if which == "A":
            code = self._convert("TO_A")
        elif which == "B":
            code = self._convert("TO_B")
        elif which == "C":
            code = self._convert("TO_C")
        self._charset = which
        return [code]

    def _maybe_switch_charset(self, pos):
        char = self.code[pos]
        next_ = self.code[pos : pos + 10]

        def look_next():
            digits = 0
            for c in next_:
                if c.isdigit():
                    digits += 1
                else:
                    break
            return digits > 3

        codes = []
        if self._charset == "C" and not char.isdigit():
            if char in code128.B:
                codes = self._new_charset("B")
            elif char in code128.A:
                codes = self._new_charset("A")
            if len(self._buffer) == 1:
                codes.append(self._convert(self._buffer[0]))
                self._buffer = ""
        elif self._charset == "B":
            if look_next():
                codes = self._new_charset("C")
            elif char not in code128.B and char in code128.A:
                codes = self._new_charset("A")
        elif self._charset == "A":
            if look_next():
                codes = self._new_charset("C")
            elif char not in code128.A and char in code128.B:
                codes = self._new_charset("B")
        return codes

    def _convert(self, char):
        if self._charset == "A":
            return code128.A[char]
        if self._charset == "B":
            return code128.B[char]
        if self._charset == "C":
            if char in code128.C:
                return code128.C[char]
            if char.isdigit():
                self._buffer += char
                if len(self._buffer) == 2:
                    value = int(self._buffer)
                    self._buffer = ""
                    return value
                return None
            return None
        return None

    def _try_to_optimize(self, encoded):
        if encoded[1] in code128.TO:
            encoded[:2] = [code128.TO[encoded[1]]]
        return encoded

    def _calculate_checksum(self, encoded):
        cs = [encoded[0]]
        for i, code_num in enumerate(encoded[1:], start=1):
            cs.append(i * code_num)
        return sum(cs) % 103

    def _build(self):
        encoded = [code128.START_CODES[self._charset]]
        for i, char in enumerate(self.code):
            print(encoded)
            encoded.extend(self._maybe_switch_charset(i))
            code_num = self._convert(char)
            if code_num is not None:
                encoded.append(code_num)
        # Finally look in the buffer
        if len(self._buffer) == 1:
            encoded.extend(self._new_charset("B"))
            encoded.append(self._convert(self._buffer[0]))
            self._buffer = ""
        return self._try_to_optimize(encoded)

    def build(self):
        encoded = self._build()
        encoded.append(self._calculate_checksum(encoded))
        code = ""
        for code_num in encoded:
            code += code128.CODES[code_num]
        code += code128.STOP
        code += "11"
        return [code]

    def render(self, writer_options=None, text=None):
        options = {"module_width": MIN_SIZE, "quiet_zone": MIN_QUIET_ZONE}
        options.update(writer_options or {})
        return super().render(options, text)


class Gs1_128(Code128):  # noqa: N801
    """
    following the norm, a gs1-128 barcode is a subset of code 128 barcode,
    it can be generated by prepending the code with the FNC1 character
    https://en.wikipedia.org/wiki/GS1-128
    https://www.gs1-128.info/
    """

    name = "GS1-128"

    FNC1_CHAR = "\xf1"

    def __init__(self, code, writer=None) -> None:
        code = self.FNC1_CHAR + code
        super().__init__(code, writer)

    def get_fullcode(self):
        return super().get_fullcode()[1:]


class Gs1_128_AI(Code128):
    name = "GS1-128_AI"
    FNC1_CHAR = "\xf1"
    # FC_CHAR = "\x1d"
    # for optimalization reasons it is reasonable to use FNC1_CHAR as separator
    # as FNC1_CHAR is present in all three charsets
    FC_CHAR = FNC1_CHAR

    # Application_Identifiers: AI name: AI code
    AI_NAME_TO_CODE = {'SSCC': '00', 'GTIN': '01', 'CONTENT': '02', 'BATCH/LOT': '10', 'BEST_BEFORE:': '15',
                       'PROD_DATE': '11', 'DUE_DATE': '12', 'PACK_DATE': '13', 'BEST_BEFORE': '15', 'SELL_BY': '16',
                       'USE_BY_OR_EXPIRY': '17', 'VARIANT': '20', 'SERIAL': '21', 'CPV': '22', 'TPX': '235',
                       'ADDITIONAL_ID': '240', 'CUST_PART_NO': '241', 'MTO_VARIANT': '242', 'PCN': '243',
                       'SECONDARY_SERIAL': '250', 'REF_TO_SOURCE': '251', 'GTDI': '253', 'GLM_EXTENSION': '254',
                       'GCN': '255', 'VAR_COUNT': '30', 'COUNT': '37'}

    AI_WITH_DECIMAL_VALS = {'NET_WEIGHT_M': '310', 'LENGTH_m': '311', 'WIDTH_M': '312', 'HEIGHT_M': '313',
                            'AREA_M2': '314', 'NET_VOLUME_L': '315', 'NET_VOLUME_M3': '316', 'NET_WEIGHT_LB': '320',
                            '321': 'LENGTH_I', '322': 'LENGTH_F', '323': 'LENGTH_Y',
                            '324': 'WIDTH_I', '325': 'WIDTH_F', '326': 'WIDTH_Y', '327': 'HEIGHT_I', '328': 'HEIGHT_F',
                            '329': 'HEIGHT_Y', 'GROSS_WEIGHT_KG': '330', 'LENGTH_M_LOG': '331', 'WIDTH_M_LOG': '332',
                            'HEIGHT_M_LOG': '333', 'AREA_M2_LOG': '334', 'VOLUME_L_LOG': '335', 'VOLUME_M3_LOG': '336',
                            'KG_PER_M2': '337', 'GROSS_WEIGHT_LB': '340', 'LENGTH_I_LOG': '341', 'LENGTH_F_LOG': '342',
                            'LENGTH_Y_LOG': '343', 'WIDTH_I_LOG': '344', 'WIDTH_F_LOG': '345', 'WIDTH_Y_LOG': '346',
                            'HEIGHT_I_LOG': '347', 'HEIGHT_F_LOG': '348', 'HEIGHT_Y_LOG': '349', 'AREA_I2': '350',
                            'AREA_F2': '351', 'AREA_Y2': '352', 'AREA_I2_LOG': '353', 'AREA_F2_LOG': '354',
                            'AREA_Y2_LOG': '355', 'NET_WEIGHT_T': '356', 'NET_VOLUME_OZ': '357', 'NET_VOLUME_Q': '360',
                            'NET_VOLUME_G': '361', 'VOLUME_Q_LOG': '362', 'VOLUME_G_LOG': '363', 'VOLUME_I3': '364',
                            'VOLUME_F3': '365', 'VOLUME_Y3': '366', 'VOLUME_I3_LOG': '367', 'VOLUME_F3_LOG': '368',
                            'VOLUME_Y3_LOG': '369', 'AMOUNT_COMMON_CURRENCY': '390',
                            'AMOUNT_CURRENCY_SPEC': '391', 'PRICE_COMMON_CURRENCY': '392', 'PRICE_CURRENCY_SPEC': '393',
                            'PRCNT_OFF': '394', 'PRICE_UOM': '395'
                            }
    
    AI_WITH_FNC1 = {'10', '21', '22', '235', '240', '241', '242', '243', '250', '251', '253', '254', '255',
                    '30', '37', '390', '391', '392', '393', '394', '395', '400', '401', '402', '403', '420', '421',
                    '422', '423', '424', '425', '426', '427', '4300', '4301', '4302', '4303', '4304', '4305', '4306',
                    '4307', '4308', '4309', '4330', '4331', '4332', '4333', '7001', '7002', '7003', '7004', '7005',
                    '7006', '7007', '7008', '7009', '7010', '7011', '7020', '7021', '7022', '7023', '703', '7040',
                    '710', '711', '712', '713', '714', '715', '723', '7240', '7241', '7242', '8001', '8002', '8003',
                    '8004', '8005', '8006', '8007', '8008', '8009', '8010', '8011', '8012', '8013', '8017', '8018',
                    '8019', '8020', '8030', '8110', '8026', '8111', '8112', '8200', '90', '91', '92', '93', '94', '95',
                    '96', '97', '98', '99'
                    }
    AI_VS_FIXED_LENGTH = {'00': 18, '01': 14, '02': 14, '11': 6, '12': 6, '13': 6, '15': 6, '16': 6, '17': 6, '20': 2}
    AI_VS_FIXED_LENGTH_WITH_DECIMAL = {'310', '311', '312', '313', '314', '315', '316', '320', '321', '322', '323',
                                       '324', '325', '326', '327', '328', '329', '330', '331', '332', '333', '334',
                                       '335', '336', '337'}

    def __init__(self, code, sorted_ais=True, writer=None) -> None:
        self.sorted_ais = sorted_ais
        self.code = None
        self.literal_code = None
        self.ai_value = None
        if isinstance(code, str):
            if self.check_if_code_correct(code):
                self.ai_value = self.get_ai_and_vals_from_brackets(code)
            else:
                self.literal_code = code
        elif isinstance(code, tuple) or isinstance(code, list):
            self.ai_value = list()
            for ai_val in code:
                self.ai_value.append(self.get_code_and_val(ai_val[0], ai_val[1]))
        else:
            print('Code for barcode must be either as string or tuple/list (ai, value).')
            return
        if self.literal_code is not None:
            self.code = self.literal_code
        else:
            self.code = self.create_code()
        super().__init__(self.code, writer)
        self._charset = self._guess_charset(self.code[1:])

    def set_sorted_ais(self, value):
        self.sorted_ais = value
        if not self.literal_code:
            self.code = self.create_code()

    def get_code_and_val(self, ai, val):
        if ai in self.AI_NAME_TO_CODE:
            ai = self.AI_NAME_TO_CODE[ai]
        if ai in self.AI_VS_FIXED_LENGTH:
            if len(val) != self.AI_VS_FIXED_LENGTH[ai]:
                if ai in ('11', '12', '13', '15', '16', '17') and not self.is_date_format_correct(val):
                    print('For AI %s correct date format is: YYMMDD. If only year and month is provided, '
                          'then use 00 for days' % ai)
                else:
                    print('For AI %s, the length of value should be %s.' % (ai, val))
            return ai, val
        elif 3 <= len(ai) <= 4 and ai[0:3] in self.AI_VS_FIXED_LENGTH_WITH_DECIMAL:
            return self.get_val_for_ai_with_fixed_length_decimals(ai, val)
        else:
            return ai, val

    @staticmethod
    def check_if_code_correct(code_with_brackets):
        # correct code is when all AI are surounded with brackets, and values are not, let's just check it
        if not code_with_brackets:
            return False
        in_bracket = 0
        for letter in code_with_brackets:
            if letter not in '()':
                continue
            elif letter == '(':
                in_bracket += 1
            elif letter == ')':
                in_bracket -= 1
        return in_bracket == 0

    @staticmethod
    def get_ai_and_vals_from_brackets(code_with_brackets):
        ais_vals_list = list()
        for ais_vals in code_with_brackets.split('('):
            if ais_vals:
                ais_vals_list.append(tuple(ais_vals.split(')')))
        return tuple(ais_vals_list)

    def get_val_for_ai_with_fixed_length_decimals(self, ai, val):
        if ai[0:3] not in self.AI_VS_FIXED_LENGTH_WITH_DECIMAL:
            return ai, val
        # if len(ai) == 3, then we need co calculate forth digig - decimal place
        try:
            num_val = float(val)
        except ValueError:
            print('For AI: %s only number values are possible, %s was provided.' % (ai, val))
            return ai + '0', val
        # if we provide 3 digits, then the forth needs to be calculated according to value provided
        if len(ai) == 3:
            # case 1 val is integer number
            if '.' not in val:
                if len(val) < 6:
                    # print('For AI: %s 6 number length is required, %s was provided.' % (ai, val))
                    # print('Filing missing gaps with 0.')
                    val = val.zfill(6)
                elif len(val) > 6:
                    print('For AI: %s 6 number length is required, %s was provided.' % (ai, val))
                return ai + '0', val[0:6]
            else:
                main_part, fraction_part = val.split('.', 1)
                if len(val) < 7:
                    for zeros_to_add in range(7-len(val)):
                        fraction_part += '0'
                elif len(val) > 7:
                    if len(main_part) > 6:
                        return ai + '0', main_part[0:6]
                    fr_to_cut = 6 - len(main_part)
                    fraction_part = fraction_part[0:fr_to_cut]
                return ai + str(len(fraction_part)), main_part + fraction_part
        if len(ai) == 4:
            pass
        else:
            print('AI: %s too long, only 4 digits allowed' % ai)
            return ai, val

    def is_fnc1_required(self, ai):
        return ai in self.AI_WITH_FNC1

    @staticmethod
    def is_date_format_correct(self, date):
        # let's check if date is in correct format, correct format is
        # YY - year, as the last two digits - required field
        # MM - months, as two digits, only values 01-12 accepted - required field
        # DD - days, if not necessary then use 00
        months_days = {1: 31, 2: 29, 3: 31, 4: 30, 5: 31, 6: 30, 7: 31, 8: 31, 9: 30, 10: 31, 11: 30, 12: 31}
        if len(date) < 4:
            return False
        year = date[0:2]
        month = date[2:4]
        day = date[4:] if len(date) > 4 else ''
        return_val = True
        if not year.isdigit():
            print('Year value incorrect, only numbers allowed: %s' % date[0:2])
            return_val = False
        if not (month.isdigit() and 1 <= int(month) <= 12):
            print('Month value incorrect, only numbers from range 01-12 allowed: %s' % date[0:2])
            return_val = False
        if not(day and day.isdigit() and months_days[int(month)] > int(day)):
            print('Day value incorrect, only number allowed and number of days should not exceed %s' %
                  str(months_days[int(month)]))
            return_val = False
        return return_val

    def create_code(self):
        ais_with_nfc1 = ''
        ais_without_nfc1 = ''
        for ai, value in self.ai_value:
            if self.sorted_ais:
                if self.is_fnc1_required(ai):
                    ais_with_nfc1 += ai + value + self.FC_CHAR
                else:
                    ais_without_nfc1 += ai + value
            else:
                ais_with_nfc1 += ai + value
                if self.is_fnc1_required(ai):
                    ais_with_nfc1 += self.FC_CHAR
        if ais_with_nfc1.endswith(self.FC_CHAR):
            ais_with_nfc1 = ais_with_nfc1[0:-1]
        return self.FNC1_CHAR + ais_without_nfc1 + ais_with_nfc1

    def get_fullcode(self):
        # return super().get_fullcode()[1:]
        return self.get_hri_text()

    def get_fullcode_with_ai_description(self):
        code_to_ai_name = {code: val for val, code in self.AI_NAME_TO_CODE.items()}
        codewith_dec_to_ai_name = {code: val for val, code in self.AI_WITH_DECIMAL_VALS.items()}
        for ai, val in self.ai_value:
            if ai in code_to_ai_name:
                print('%s: %s ' % (code_to_ai_name[ai], val))
            elif ai[0:3] in codewith_dec_to_ai_name:
                print('%s: %s ' % (codewith_dec_to_ai_name[ai[0:3]], val))
            else:
                print('%s: %s ' % (ai, val))

    def get_hri_text(self):
        # get Human Readable Interpretation text
        text_with_nfc1 = ''
        text_without_nfc1 = ''
        for ai, val in self.ai_value:
            if self.sorted_ais:
                if self.is_fnc1_required(ai):
                    text_with_nfc1 += '(' + ai + ')' + val
                else:
                    text_without_nfc1 += '(' + ai + ')' + val
            else:
                text_with_nfc1 += '(' + ai + ')' + val
        return text_without_nfc1 + text_with_nfc1

    def render(self, writer_options=None, text=None):
        self.code = self.create_code()
        if text is not None and text:
            self.get_fullcode()
        options = {"module_width": MIN_SIZE * 2.5, "quiet_zone": MIN_QUIET_ZONE, "font_size": 10, 'center_text': True,
                   'text_distance': 5}
        options.update(writer_options or {})
        return super().render(options, text)

# For pre 0.8 compatibility
PZN = PZN7
