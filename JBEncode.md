Je to knihovna odpovídající JBEncode v JavaScriptu a PHP

Použití:

```python
from jbencode import JBEncode

data = b"Hello world!"
pwd = "myStrongKey"

enc = JBEncode.encode_b64(data, pwd)
print("Encoded:", enc)

dec = JBEncode.decode_b64(enc, pwd)
print("Decoded:", dec.decode())
```