import random
import struct
import base64

__VERSION__ = "1.0.0"

class JBEncode:
    crc_pattern = 0xAAAA

    @staticmethod
    def _bit_rotate_left(val, rbits)-> int:
        """Bitová rotace doleva
        Arguments:
            val (int): hodnota k rotaci
            rbits (int): počet bitů k rotaci
        Returns:
            int: Rotované hodnoty jako byte
        """
        rbits %= 8
        return ((val << rbits) & 0xFF) | (val >> (8 - rbits))

    @staticmethod
    def _bit_rotate_right(val, rbits)-> int:
        """Bitová rotace doprava
        Arguments:
            val (int): hodnota k rotaci
            rbits (int): počet bitů k rotaci
        Returns:
            int: Rotované hodnoty jako byte
        """
        rbits %= 8
        return ((val >> rbits) | (val << (8 - rbits))) & 0xFF

    @staticmethod
    def _get_crc(buf: bytes)-> int:
        """Vypočítá CRC pro zadaný buffer
        Arguments:
            buf (bytes): buffer pro výpočet CRC
        Returns:
            int: CRC hodnota jako 16bit celé číslo
        """
        crc = JBEncode.crc_pattern
        for b in buf:
            for _ in range(8):
                x = ((crc >> 15) ^ (b >> 7)) & 1
                crc = (crc << 1) & 0xFFFF
                b = (b << 1) & 0xFF
                if x:
                    crc ^= JBEncode.crc_pattern
        return crc

    @staticmethod
    def _get_iv_from_crc(crc)-> int:
        """Vrátí počáteční pozici iv z CRC
        Arguments:
            crc (int): CRC hodnota
        Returns:
            int: počáteční pozice iv (0-7) jako byte
        """
        iv = 0
        for i in range(4):
            iv += (crc >> (i * 4)) & 0x0F
        return iv & 0x07

    @staticmethod
    def _get_pwrd_from_crc(crc)-> int:
        """Vrátí hodnotu pwrd z CRC
        Arguments:
            crc (int): CRC hodnota
        Returns:
            int: hodnota pwrd (0 nebo 1)
        """
        pwrd = 0
        for i in range(16):
            pwrd += (crc >> i) & 1
        return pwrd & 1

    @staticmethod
    def _get_xor_from_crc(crc)-> int:
        """Vrátí počáteční hodnotu x_or z CRC
        Arguments:
            crc (int): CRC hodnota
        Returns:
            int: počáteční hodnota x_or jako byte
        """
        x_or = 0b10101010
        x_or ^= (crc >> 8) & 0xFF
        x_or ^= crc & 0xFF
        return x_or

    @staticmethod
    def _solime(salt, buf: bytearray)-> None:
        """Solí buffer pomocí zadané soli
        Arguments:
            salt (int): sůl jako 16bit celé číslo
            buf (bytearray): buffer k solení
        Return:
            None
        """
        s8 = struct.pack("<H", salt)
        for i in range(len(buf)):
            buf[i] ^= s8[i % 2]

    @staticmethod
    def _fix_pwd(pwd: str):
        """Upraví heslo na délku násobku 8 bytů
        Arguments:
            pwd (str): původní heslo
        Returns:
            str: upravené heslo
        """
        if len(pwd) == 0:
            raise ValueError("Password is empty")
        target = ((len(pwd) + 7) // 8) * 8
        while len(pwd) < target:
            pwd += pwd[len(pwd) % len(pwd)]
        return pwd

    @staticmethod
    def encode(data: str|bytes, pwd: str, encoding:str='utf-8') -> bytes:
        """Kóduje data pomocí zadaného hesla
        Arguments:
            data (bytes): data k zakódování
            pwd (str): heslo pro kódování
        Returns:
            bytes: zakódovaná data
        """
        if encoding is not None and not isinstance(encoding, str):
            raise ValueError("decoding must be str or None")
        
        if isinstance(data, str):
            data = data.encode(encoding)
            
        if len(data) == 0:
            raise ValueError("Data are empty")
        if len(pwd) < 6:
            raise ValueError("Password too short")

        pwd = JBEncode._fix_pwd(pwd)
        salt = random.randint(0, 0xFFFF)
        ln = len(data) & 0xFFFF
        ln_full = ((ln + 2 + 7) // 8) * 8 + 8 + 6
        buf = bytearray(ln_full)

        struct.pack_into("<H", buf, 0, ln)
        buf[2:2+ln] = data

        t = random.getrandbits(32)
        t8 = struct.pack("<I", t)
        ln8 = ((ln + 2 + 7) // 8) * 8 + 8
        for i in range(2 + ln, ln8):
            buf[i] = t8[i % 4]

        crc = JBEncode._get_crc(buf[:ln8]) & 0xFFFF
        iv = JBEncode._get_iv_from_crc(crc) & 0x07
        pwrd = JBEncode._get_pwrd_from_crc(crc) & 0x01
        x_or = JBEncode._get_xor_from_crc(crc) & 0xFF

        pos = iv
        for _ in range(ln8):
            if pos >= ln8:
                pos = 0
            elif pos < 0:
                pos = ln8 - 1
            p_pos = pos % len(pwd)
            buf[pos] ^= x_or
            buf[pos] ^= ord(pwd[p_pos])
            bs  = (ord(pwd[p_pos]) ^ x_or) & 0xFF
            bs1 = bs & 0x0F
            bs2 = (bs >> 4) & 0x0F
            buf[pos] = JBEncode._bit_rotate_left(buf[pos] & 0xFF, bs1) & 0xFF
            buf[pos] = JBEncode._bit_rotate_right(buf[pos] & 0xFF, bs2) & 0xFF
            x_or = (x_or ^ buf[pos]) & 0xFF
            pos = pos - 1 if pwrd else pos + 1

        x_or2 = ((x_or << 8) | x_or) & 0xFFFF
        crc_x = (crc ^ x_or2) & 0xFFFF
        pwrd_x = ((t & 0xFFFE) | pwrd) & 0xFFFF  # uint16_t 

        #uložíme crc uint16, x_or byte, pwrd byte, salt uint16        
        help_data = struct.pack("<HBBH", crc_x, x_or, pwrd_x & 0xFF, salt)
        buf[ln8:ln8+6] = help_data

        JBEncode._solime(salt, buf[:-2])  # solíme vše kromě posledních 2 bytů (salt)
        return bytes(buf)


    @staticmethod
    def decode(buf: bytes, pwd: str, decoding:str|None='utf-8') -> bytes|str:
        """Dekóduje data pomocí zadaného hesla
        Arguments:
            buf (bytes): data k dekódování
            pwd (str): heslo pro dekódování
            decode (str|None): pokud None tak se vrací bytes, jinak se vrací str s daným encodingem
        Returns:
            bytes|str: dekódovaná data nebo str pokud decoding není None
        """
        if decoding is not None and not isinstance(decoding, str):
            raise ValueError("decoding must be str or None")
        if len(buf) == 0:
            raise ValueError("Data are empty")
        if len(pwd) < 6:
            raise ValueError("Password too short")

        pwd = JBEncode._fix_pwd(pwd)
        ln_enc = len(buf) - 6
        buf = bytearray(buf)

        # 1) NEJDŘÍV přečíst jen salt (poslední 2 byty help_data nejsou solené)
        salt = struct.unpack_from("<H", buf, ln_enc + 4)[0]

        # 2) Odsolit celý buffer kromě posledních 2 bytů
        JBEncode._solime(salt, buf[:-2])

        # 3) Teď teprve přečíst crc_x, x_or, pwrd_x z ODsolených dat
        crc_x, x_or, pwrd_x = struct.unpack_from("<HBB", buf, ln_enc)
        x_or  &= 0xFF
        crc_x &= 0xFFFF

        x_or2 = ((x_or << 8) | x_or) & 0xFFFF
        crc   = (crc_x ^ x_or2) & 0xFFFF
        pwrd  = pwrd_x & 0x01
        iv    = JBEncode._get_iv_from_crc(crc)
        ln8   = ln_enc

        pos = iv
        pos = pos + 1 if pwrd else pos - 1
        if pos < 0:
            pos = ln8 - 1

        for _ in range(ln8):
            if pos >= ln8:
                pos = 0
            elif pos < 0:
                pos = ln8 - 1

            p_pos = pos % len(pwd) & 0xFFFF
            x_or = (x_or ^ buf[pos]) & 0xFF
            bs  = (ord(pwd[p_pos]) ^ x_or) & 0xFF
            bs1 = bs & 0x0F
            bs2 = ( (bs & 0xF0 ) >> 4) & 0x0F

            # Inverzní pořadí + směry rotací oproti encode
            buf[pos] = JBEncode._bit_rotate_left (buf[pos] & 0xFF, bs2) & 0xFF
            buf[pos] = JBEncode._bit_rotate_right(buf[pos] & 0xFF, bs1) & 0xFF

            buf[pos] ^= ord(pwd[p_pos])
            buf[pos] ^= x_or
            pos = pos + 1 if pwrd else pos - 1

        if x_or != (JBEncode._get_xor_from_crc(crc) & 0xFF):
            raise ValueError("KeyX invalid")

        ln = struct.unpack_from("<H", buf, 0)[0]
        data = buf[2:2+ln]
        crc_check = JBEncode._get_crc(buf[:ln8]) & 0xFFFF
        if crc_check != crc:
            raise ValueError("CRC invalid")

        if decoding is not None:
            return data.decode(decoding)
        else:
            return bytes(data)

    @staticmethod
    def encode_b64(data: str|bytes, pwd: str, encoding:str='utf-8') -> str:
        """Kóduje data do base64 pomocí zadaného hesla
        Arguments:
            data (bytes): data k zakódování
            pwd (str): heslo pro kódování
            encoding (str): encoding pro převod str na bytes, defaultně 'utf-8'
        Returns:
            str: zakódovaná data v base64
        """
        return base64.b64encode(JBEncode.encode(data, pwd)).decode()

    @staticmethod
    def decode_b64(data_b64: str, pwd: str, decoding:bool=True, encoding:str='utf-8') -> bytes|str:
        """Dekóduje data z base64 pomocí zadaného hesla
        Arguments:
            data_b64 (str): data v base64 k dekódování
            pwd (str): heslo pro dekódování
            decode (str|None): pokud je None tak se vrací bytes, jinak se vrací str s daným encodingem
        Returns:
            bytes|str: dekódovaná data nebo str pokud decoding není None
        """
        raw = base64.b64decode(data_b64)
        return JBEncode.decode(raw, pwd, decodeing if decoding else None)
