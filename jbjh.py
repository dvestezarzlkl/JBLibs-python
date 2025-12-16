
from typing import Union
from datetime import datetime

"""viz MD dokumentace"""

class JBJH:
    
    @staticmethod
    def is_int(s: any,throw:bool=False)-> Union[int,None]:
        """Zkontroluje, zda je hodnota typu int.

        Args:
            s (any): Hodnota k otestování.
            throw (bool, optional): Pokud je True, vyhodí výjimku při neúspěchu. Defaults to False.
        Returns:
            Union[int,None]: Vrací int, pokud je hodnota typu int, jinak None.
        """
        if isinstance(s,int):
            return s
        try:
            val=int(s)
            return val
        except:
            if throw:
                raise ValueError(f"Hodnota '{s}' není typu int.")
            return None
        
    @staticmethod
    def is_float(s: any,throw:bool=False)-> Union[float,None]:
        """Zkontroluje, zda je hodnota typu float.

        Args:
            s (any): Hodnota k otestování.
            throw (bool, optional): Pokud je True, vyhodí výjimku při neúspěchu. Defaults to False.
        Returns:
            Union[float,None]: Vrací float, pokud je hodnota typu float, jinak None.
        """
        if isinstance(s,float):
            return s
        try:
            val=float(s)
            return val
        except:
            if throw:
                raise ValueError(f"Hodnota '{s}' není typu float.")
            return None
        
    @staticmethod
    def is_str(s: any,throw:bool=False)-> Union[str,None]:
        """Zkontroluje, zda je hodnota typu str.

        Args:
            s (any): Hodnota k otestování.
            throw (bool, optional): Pokud je True, vyhodí výjimku při neúspěchu. Defaults to False.
        Returns:
            Union[str,None]: Vrací str, pokud je hodnota typu str, jinak None.
        """
        if isinstance(s,str):
            return s
        try:
            if isinstance(s,bytes):
                return s.decode('utf-8')            
            return str(s)
        except:
            if throw:
                raise ValueError(f"Hodnota '{s}' není typu str.")
            return None
        
    @staticmethod
    def is_bool(s: any,throw:bool=False)-> Union[bool,None]:
        """Zkontroluje, zda je hodnota typu bool.

        Args:
            s (any): Hodnota k otestování.
            throw (bool, optional): Pokud je True, vyhodí výjimku při neúspěchu. Defaults to False.
        Returns:
            Union[bool,None]: Vrací bool, pokud je hodnota typu bool, jinak None.
        """
        if isinstance(s,bool):
            return s
        try:
            if str(s).lower() in ['true','1','yes','y']:
                return True
            elif str(s).lower() in ['false','0','no','n']:
                return False
            else:
                raise ValueError()
        except:
            if throw:
                raise ValueError(f"Hodnota '{s}' není typu bool.")
            return None

    @staticmethod
    def is_list(s: any,throw:bool=False)-> Union[list,None]:
        """Zkontroluje, zda je hodnota typu list.

        Args:
            s (any): Hodnota k otestování.
            throw (bool, optional): Pokud je True, vyhodí výjimku při neúspěchu. Defaults to False.
        Returns:
            Union[list,None]: Vrací list, pokud je hodnota typu list, jinak None.
        """
        if isinstance(s,list):
            return s
        try:
            val=list(s)
            return val
        except:
            if throw:
                raise ValueError(f"Hodnota '{s}' není typu list.")
            return None
        
    @staticmethod
    def is_dict(s: any,throw:bool=False)-> Union[dict,None]:
        """Zkontroluje, zda je hodnota typu dict.

        Args:
            s (any): Hodnota k otestování.
            throw (bool, optional): Pokud je True, vyhodí výjimku při neúspěchu. Defaults to False.
        Returns:
            Union[dict,None]: Vrací dict, pokud je hodnota typu dict, jinak None.
        """
        if isinstance(s,dict):
            return s
        try:
            val=dict(s)
            return val
        except:
            if throw:
                raise ValueError(f"Hodnota '{s}' není typu dict.")
            return None
        
    @staticmethod
    def is_tuple(s: any,throw:bool=False)-> Union[tuple,None]:
        """Zkontroluje, zda je hodnota typu tuple.

        Args:
            s (any): Hodnota k otestování.
            throw (bool, optional): Pokud je True, vyhodí výjimku při neúspěchu. Defaults to False.
        Returns:
            Union[tuple,None]: Vrací tuple, pokud je hodnota typu tuple, jinak None.
        """
        if isinstance(s,tuple):
            return s
        try:
            val=tuple(s)
            return val
        except:
            if throw:
                raise ValueError(f"Hodnota '{s}' není typu tuple.")
            return None
        
    @staticmethod
    def is_set(s: any,throw:bool=False)-> Union[set,None]:
        """Zkontroluje, zda je hodnota typu set.

        Args:
            s (any): Hodnota k otestování.
            throw (bool, optional): Pokud je True, vyhodí výjimku při neúspěchu. Defaults to False.
        Returns:
            Union[set,None]: Vrací set, pokud je hodnota typu set, jinak None.
        """
        if isinstance(s,set):
            return s
        try:
            val=set(s)
            return val
        except:
            if throw:
                raise ValueError(f"Hodnota '{s}' není typu set.")
            return None
        
    @staticmethod
    def is_bytes(s: any,throw:bool=False)-> Union[bytes,None]:
        """Zkontroluje, zda je hodnota typu bytes.

        Args:
            s (any): Hodnota k otestování.
            throw (bool, optional): Pokud je True, vyhodí výjimku při neúspěchu. Defaults to False.
        Returns:
            Union[bytes,None]: Vrací bytes, pokud je hodnota typu bytes, jinak None.
        """
        if isinstance(s,bytes):
            return s            
        try:
            if isinstance(s,str):
                return s.encode('utf-8')
            else:
                return bytes(s)
        except:
            if throw:
                raise ValueError(f"Hodnota '{s}' není typu bytes.")
            return None
        
    @staticmethod
    def is_intArray(s: any,returnAsString:bool=True,throw:bool=False)-> Union[bytearray,None]:
        """Zkontroluje, zda je hodnota typu bytearray.
        Vhodné pro vstupy jako "1,2,3" (např stringy uložené v DB) nebo [1,2,3] atp.

        Args:
            s (any): Hodnota k otestování. Může být i string reprezentující čísla oddělená čárkou.
            throw (bool, optional): Pokud je True, vyhodí výjimku při neúspěchu. Defaults to False.
            returnAsString (bool, optional): Pokud je True výstup bude string int oddělených čárkou.  
                Defaul je true.  
                Pokud false tak je výstup int[].
        Returns:
            Union[str,List[int],None]: Vrací int[] nebo str
        """
        intList:list[int]=[]
        try:
            if (s:=JBJH.is_str(s)) is not None:
                parts=s.split(',')
                for p in parts:
                    if(val:=JBJH.is_int(p.strip()) ) is None:
                        if throw:
                            raise ValueError(f"Vstup obsahuje hodnotu, která není int: '{p.strip()}'")
                        return None
                    intList.append(val)
            else:
                if ( s:=JBJH.is_list(s,throw=True) ) is None:
                    if throw:
                        raise ValueError(f"Hodnota '{s}' není platné pole intů.")
                    return None
                for item in s:
                    if(val:=JBJH.is_int(item,throw=True) ) is None:
                        if throw:
                            raise ValueError(f"Vstup obsahuje hodnotu, která není int: '{item}'")
                        return None
                    intList.append(val)
            if returnAsString:
                return ','.join( str(i) for i in intList )
            else:
                return intList
        except Exception as e:
            if throw:
                raise ValueError(f"Hodnota '{s}' není platné pole intů. Chyba: {e}")
            return None

    @staticmethod
    def is_strArray(s: any,returnAsString:bool=True,throw:bool=False)-> Union[str,list,None]:
        """Zkontroluje, zda je hodnota typu list stringů.
        Vhodné pro vstupy jako "a,b,c" (např stringy uložené v DB) nebo ["a","b","c"] atp.

        Args:
            s (any): Hodnota k otestování. Může být i string reprezentující stringy oddělené čárkou.
            throw (bool, optional): Pokud je True, vyhodí výjimku při neúspěchu. Defaults to False.
            returnAsString (bool, optional): Pokud je True výstup bude string stringů oddělených čárkou.  
                Defaul je true.  
                Pokud false tak je výstup str[].
        Returns:
            Union[str,List[str],None]: Vrací str[] nebo str
        """
        strList:list[str]=[]
        try:
            if (s:=JBJH.is_str(s)) is not None:
                parts=s.split(',')
                for p in parts:
                    strList.append(p.strip())
            else:
                if ( s:=JBJH.is_list(s,throw=True) ) is None:
                    if throw:
                        raise ValueError(f"Hodnota '{s}' není platné pole stringů.")
                    return None
                for item in s:
                    if(val:=JBJH.is_str(item,throw=True) ) is None:
                        if throw:
                            raise ValueError(f"Vstup obsahuje hodnotu, která není string: '{item}'")
                        return None
                    strList.append(val)
            if returnAsString:
                return ','.join( str(i) for i in strList )
            else:
                return strList
        except Exception as e:
            if throw:
                raise ValueError(f"Hodnota '{s}' není platné pole stringů. Chyba: {e}")
            return None
        
    @staticmethod
    def is_dateTime(s: any, throw: bool = False) -> Union[datetime, None]:
        """Bezpečný převod na datetime."""
        if isinstance(s, datetime):
            return s

        s = str(s).strip()

        formats = [
            None,  # ISO (řeší se zvlášť)
            "%Y-%m-%d %H:%M:%S",
            "%d.%m.%Y %H:%M:%S",
            "%Y-%m-%d",
            "%d.%m.%Y",
        ]

        # ISO 8601
        try:
            dt = datetime.fromisoformat(s)
            return dt
        except Exception:
            pass

        # Ostatní formáty
        for fmt in formats[1:]:
            try:
                dt = datetime.strptime(s, fmt)
                if "H" not in fmt:
                    return datetime(dt.year, dt.month, dt.day, 0, 0, 0)
                return dt
            except Exception:
                continue

        if throw:
            raise ValueError(f"Hodnota '{s}' není typu datetime.")
        return None
    
    @staticmethod
    def is_date(s: any,throw:bool=False)-> Union['datetime.date',None]:
        """Zkontroluje, zda je hodnota typu date.
        Akceptuje např:
            - ISO 8601 formát: '2023-10-05'
            - 'YYYY-MM-DD' formát: '2023-10-05' (MySQL styl)
            - CZ styl: '05.10.2023'

        Args:
            s (any): Hodnota k otestování
            throw (bool, optional): Pokud je True, vyhodí výjimku při neúspěchu. Defaults to False.
        Returns:
            Union[datetime.date,None]: Vrací date, pokud je hodnota typu date, jinak None.
        """
        if isinstance(s,datetime):
            return s.date()
        if isinstance(s,datetime.date):
            return s
        try:
            dt=datetime.fromisoformat(str(s))
            return dt.date()
        except:
            pass
        try:
            dt=datetime.strptime(str(s), '%Y-%m-%d')
            return dt.date()
        except:
            pass
        try:
            dt=datetime.strptime(str(s), '%d.%m.%Y')
            return dt.date()
        except:
            if throw:
                raise ValueError(f"Hodnota '{s}' není typu date.")
            return None

    @staticmethod
    def constrain_int(value:int,minValue:int,maxValue:int)-> int:
        """Omezí hodnotu int na zadaný rozsah.

        Args:
            value (int): Hodnota k omezení.
            minValue (int): Minimální povolená hodnota.
            maxValue (int): Maximální povolená hodnota.
        Returns:
            int: Omezená hodnota.
        """
        if not isinstance(value,int):
            raise ValueError("Hodnota musí být typu int.")
        if not isinstance(minValue,int):
            raise ValueError("minValue musí být typu int.")
        if not isinstance(maxValue,int):
            raise ValueError("maxValue musí být typu int.")
        if minValue >= maxValue:
            raise ValueError("minValue musí být menší než maxValue.")
        if value < minValue:
            return minValue
        if value > maxValue:
            return maxValue
        return value
    
    @staticmethod
    def constrain_float(value:float,minValue:float,maxValue:float)-> float:
        """Omezí hodnotu float na zadaný rozsah.

        Args:
            value (float): Hodnota k omezení.
            minValue (float): Minimální povolená hodnota.
            maxValue (float): Maximální povolená hodnota.
        Returns:
            float: Omezená hodnota.
        """
        if not isinstance(value,float):
            raise ValueError("Hodnota musí být typu float.")
        if not isinstance(minValue,float):
            raise ValueError("minValue musí být typu float.")
        if not isinstance(maxValue,float):
            raise ValueError("maxValue musí být typu float.")
        if minValue >= maxValue:
            raise ValueError("minValue musí být menší než maxValue.")
        if value < minValue:
            return minValue
        if value > maxValue:
            return maxValue
        return value
    
    @staticmethod
    def checkMinMax(value:float|int,minValue:float|int,maxValue:float|int,throw:bool=False)-> bool:
        """Zkontroluje, zda je minValue menší než maxValue. Vrací True/False nebo vyhodí výjimku.
        Args:
            value (float|int): Hodnota k otestování.
            minValue (float): Minimální hodnota.
            maxValue (float): Maximální hodnota.
            throw (bool, optional): Pokud je True, vyhodí výjimku při neúspěchu. Defaults to False.
        Returns:
            bool: True pokud je minValue < maxValue, jinak False.
        """
        try:
            if not isinstance(minValue,(int,float)):
                raise ValueError("minValue musí být číslo.")
            if not isinstance(maxValue,(int,float)):
                raise ValueError("maxValue musí být číslo.")
            if not isinstance(value,(int,float)):
                raise ValueError("value musí být číslo.")
            if minValue >= maxValue:
                if throw:
                    raise ValueError("minValue musí být menší než maxValue.")
                return False
            if value < minValue or value > maxValue:
                if throw:
                    raise ValueError(f"value musí být mezi {minValue} a {maxValue}.")
                return False
            return True
        except Exception as e:
            if throw:
                raise e
            return False