# A2LParser
A minimal Python parser for ASAP2 (.a2l) files, tailored to extract key data from project-specific A2L files. This parser parses and organizes the A2L content into a structured Python data model, enabling easy inspection and further processing.

# Features
- Parses key ASAP2 blocks and structures:

    **Project and Module**
  
    **XCPplus → PROTOCOL_LAYER**
  
    **DAQ (including events)**
  
    **XCP_ON_CAN transport layer parameters (including CAN FD)**
  
    **Memory segments**

    **AXIS_PTS (calibration axes)**
  
    **MEASUREMENTS**
  
    **CHARACTERISTICS**
  
    **RECORD_LAYOUTs**
  
    **COMPU_METHODs and COMPU_VTABs**
  
    **GROUPs and FUNCTIONs (with local measurements / references)**
- Supports partial ASAP2 dialects tailored to your files – not a full ASAP2 grammar parser.

- Provides simple Python dataclasses representing blocks with rich field extraction.

- Converts parsed data into JSON-like Python dictionaries for easier export or analysis.

Usage
Ensure Python 3.7+ is installed.


```batch
pip install pya2lparser
```



```python
from a2lparser.a2l_parser import A2LParser

parser = A2LParser()
model = parser.parse_file("your_file.a2l")

print(f"Project: {model.project_name}")
print(f"Module: {model.module_name}")
print(f"Number of characteristics: {len(model.characteristics)}")
# Export as dict or JSON
model_dict = model.to_dict()
```


## Classes and Data Model
**A2LParser**
Main parser class.

    **- parse_file(path: str)
    **- parse_text(text: str)****
**Dataclasses for parsed blocks:**

- A2LModel: Root container for the parsed data
- ProtocolLayer, DaqConfig, DaqEvent
- XcpOnCanConfig, XcpOnCanFdConfig
- MemorySegment, SegmentInfo, PageInfo
- AxisPts, Measurement, Characteristic (new)
- CompuMethod, CompuVTab
- RecordLayout, Group, Function
- A2LBlock: Generic block tree node class
## Script Structure Overview
- **Utilities:** Text preprocessing, tokenization, and conversions

- **BlockBuilder:** Reads A2L lines and builds a nested block tree based on /begin and /end lines

- **Parse functions:** Specialized parsers for known ASAP2 blocks into their respective dataclasses

- **A2LParser class:** Coordinates the parsing and assembles the final model



## Limitations
- This is a minimal parser and does not support full ASAP2 grammar.

- It's tailored to a specific dialect/structure of A2L files and may require adjustments for other variants.

- Large or complex A2L files may require optimization or deeper error handling.

## Example Output


```
Project: xxx
Module: <module_name>
Protocol Layer parsed: True
DAQ events: 5
XCP on CAN parsed: True
Memory segments: 3
AXIS_PTS: 8
Measurements: 120
Characteristics: 75
Record layouts: 10
First CHARACTERISTIC: <name> <type> 0x1234 <rec_layout> <compu_method>
First DAQ event: DaqEvent(name=...)
First AXIS_PTS: <axis_name> 0x5678
```

# License
MIT

# Contact
For issues or improvements, please raise an issue or contribute via pull requests if hosted on a repository.
