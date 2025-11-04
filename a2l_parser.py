#!/usr/bin/env python3
"""
A minimal A2L parser tailored for the provided file.
Parses and holds:
- Project and Module
- XCPplus → PROTOCOL_LAYER
- DAQ (including events)
- XCP_ON_CAN (transport layer parameters, including CAN FD)
- Memory segments
- AXIS_PTS (calibration axes)
- MEASUREMENTs
- CHARACTERISTICs  <-- NEW
- RECORD_LAYOUTs
- COMPU_METHODs and COMPU_VTABs
- GROUPs and FUNCTIONs (loc/refs)

Note: This is not a full ASAP2 grammar parser. It is designed to parse the specific structure
in the user-provided A2L. You may need to adjust handlers to your dialect/variants.

Usage:
    model = A2LParser().parse_file("your.a2l")
    print(model.project_name, model.module_name)
    print(f"Characteristics: {len(model.characteristics)}")
    print(f"DAQ events: {len(model.daq_events)}")
    print(f"AXIS_PTS: {len(model.axis_pts)}")
    print(f"Measurements: {len(model.measurements)}")
    # Export to JSON-like dict
    import json
    print(json.dumps(model.to_dict(), indent=2))
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any, Tuple
import re
import shlex
import sys
from pathlib import Path


# --------------------------
# Utilities
# --------------------------

def strip_block_comments(text: str) -> str:
    # Remove C-style /* ... */ comments
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)

def to_int(token: str) -> Optional[int]:
    try:
        if token.lower().startswith("0x"):
            return int(token, 16)
        return int(token)
    except Exception:
        return None

def to_float(token: str) -> Optional[float]:
    try:
        return float(token)
    except Exception:
        return None

def tokenize_line(line: str) -> List[str]:
    # Handle quoted strings and plain tokens
    return shlex.split(line, posix=True)

def unquote(s: str) -> str:
    if len(s) >= 2 and ((s[0] == '"' and s[-1] == '"') or (s[0] == "'" and s[-1] == "'")):
        return s[1:-1]
    return s


# --------------------------
# Block tree representation
# --------------------------

@dataclass
class A2LBlock:
    name: str
    args: List[str] = field(default_factory=list)
    lines: List[str] = field(default_factory=list)  # raw lines inside this block (including children)
    children: List["A2LBlock"] = field(default_factory=list)

    def get_children(self, name: str) -> List["A2LBlock"]:
        return [c for c in self.children if c.name.upper() == name.upper()]

    def get_first_child(self, name: str) -> Optional["A2LBlock"]:
        kids = self.get_children(name)
        return kids[0] if kids else None


# --------------------------
# Dataclasses for structured model
# --------------------------

@dataclass
class ProtocolLayer:
    version: Optional[int] = None
    timing_values: List[int] = field(default_factory=list)  # T1..T7 etc
    max_cto: Optional[int] = None
    max_dto: Optional[int] = None
    byte_order: Optional[str] = None
    address_granularity: Optional[str] = None
    optional_cmds: List[str] = field(default_factory=list)
    communication_mode: Optional[str] = None
    master_max_bs: Optional[int] = None
    master_min_st: Optional[int] = None
    raw: List[str] = field(default_factory=list)

@dataclass
class DaqEvent:
    name: str
    short_name: Optional[str]
    event_channel_number: Optional[int]
    type: Optional[str]  # DAQ/STIM/DAQ_STIM
    max_daq_list: Optional[int]
    cycle: Optional[int]
    time_unit: Optional[int]
    priority: Optional[int]
    raw: List[str] = field(default_factory=list)

@dataclass
class DaqConfig:
    mode: Optional[str] = None  # DYNAMIC/STATIC
    max_daq: Optional[int] = None
    max_event_channel: Optional[int] = None
    min_daq: Optional[int] = None
    identification_field_type: Optional[str] = None
    odt_entry_granularity_daq: Optional[str] = None
    max_odt_entry_size_daq: Optional[int] = None
    overload_indication: Optional[str] = None
    stim_granularity: Optional[str] = None
    max_odt_entry_size_stim: Optional[int] = None
    bit_stim_supported: bool = False
    events: List[DaqEvent] = field(default_factory=list)
    raw: List[str] = field(default_factory=list)

@dataclass
class XcpOnCanFdConfig:
    max_dlc: Optional[int] = None
    data_transfer_baudrate: Optional[int] = None
    sample_point: Optional[int] = None
    btl_cycles: Optional[int] = None
    sjw: Optional[int] = None
    sync_edge: Optional[str] = None
    max_dlc_required: bool = False
    secondary_sample_point: Optional[int] = None
    tdc: Optional[str] = None
    raw: List[str] = field(default_factory=list)

@dataclass
class XcpOnCanConfig:
    version: Optional[int] = None
    can_id_broadcast: Optional[int] = None
    can_id_master: Optional[int] = None
    can_id_slave: Optional[int] = None
    can_id_get_daq_clock_multicast: Optional[int] = None
    baudrate: Optional[int] = None
    sample_point: Optional[int] = None
    sample_rate: Optional[str] = None
    btl_cycles: Optional[int] = None
    sjw: Optional[int] = None
    sync_edge: Optional[str] = None
    max_dlc_required: bool = False
    max_bus_load: Optional[int] = None
    can_fd: Optional[XcpOnCanFdConfig] = None
    raw: List[str] = field(default_factory=list)

@dataclass
class PageInfo:
    page_number: Optional[int]
    ecu_access: Optional[str]
    xcp_read_access: Optional[str]
    xcp_write_access: Optional[str]

@dataclass
class SegmentInfo:
    segment_number: Optional[int] = None
    num_pages: Optional[int] = None
    address_extension: Optional[int] = None
    compression_method: Optional[int] = None
    encryption_method: Optional[int] = None
    checksum_type: Optional[str] = None
    pages: List[PageInfo] = field(default_factory=list)
    raw: List[str] = field(default_factory=list)

@dataclass
class MemorySegment:
    name: str
    long_identifier: Optional[str]
    class_type: Optional[str]  # CODE/DATA/RESERVED/OFFLINE_DATA/CALIBRATION_VARIABLES etc
    memory_type: Optional[str]  # FLASH/ROM/RAM
    address: Optional[int]
    size: Optional[int]
    attributes: List[str] = field(default_factory=list)  # trailing -1s etc as raw
    segment_info: Optional[SegmentInfo] = None
    raw: List[str] = field(default_factory=list)

@dataclass
class AxisPts:
    name: str
    description: str
    address: Optional[int]
    input_quantity: Optional[str]
    record_layout: Optional[str]
    deposit: Optional[int]
    compu_method: Optional[str]
    max_axis_points: Optional[int]
    lower_limit: Optional[float]
    upper_limit: Optional[float]
    byte_order: Optional[str] = None
    format_str: Optional[str] = None
    symbol_link: Optional[Tuple[str, int]] = None
    raw: List[str] = field(default_factory=list)

@dataclass
class Measurement:
    name: str
    description: str
    datatype: str
    compu_method: str
    params: List[str] = field(default_factory=list)
    ecu_address: Optional[int] = None
    address: Optional[int] = None
    lower_limit: Optional[float] = None
    upper_limit: Optional[float] = None
    symbol_link: Optional[Tuple[str, int]] = None
    raw: List[str] = field(default_factory=list)

# NEW: Characteristic dataclass
@dataclass
class Characteristic:
    name: str
    description: str
    char_type: str
    address: Optional[int]
    record_layout: Optional[str]
    max_diff: Optional[float]
    compu_method: Optional[str]
    lower_limit: Optional[float]
    upper_limit: Optional[float]
    symbol_link: Optional[Tuple[str, int]] = None
    raw: List[str] = field(default_factory=list)

@dataclass
class CompuMethod:
    name: str
    description: str
    method_type: str  # e.g., RAT_FUNC
    format_str: Optional[str]
    unit: Optional[str]
    coeffs: List[float] = field(default_factory=list)
    raw: List[str] = field(default_factory=list)

@dataclass
class CompuVTab:
    name: str
    description: str
    tab_type: str  # TAB_VERB etc
    entries: List[Tuple[int, str]] = field(default_factory=list)
    raw: List[str] = field(default_factory=list)

@dataclass
class RecordLayout:
    name: str
    entries: List[str] = field(default_factory=list)
    raw: List[str] = field(default_factory=list)

@dataclass
class Group:
    name: str
    description: str
    ref_measurements: List[str] = field(default_factory=list)
    raw: List[str] = field(default_factory=list)

@dataclass
class Function:
    name: str
    description: str
    loc_measurements: List[str] = field(default_factory=list)
    raw: List[str] = field(default_factory=list)

@dataclass
class A2LModel:
    project_name: Optional[str] = None
    module_name: Optional[str] = None

    protocol_layer: Optional[ProtocolLayer] = None
    daq: Optional[DaqConfig] = None
    daq_events: List[DaqEvent] = field(default_factory=list)
    xcp_on_can: Optional[XcpOnCanConfig] = None

    memory_segments: List[MemorySegment] = field(default_factory=list)
    axis_pts: List[AxisPts] = field(default_factory=list)
    measurements: List[Measurement] = field(default_factory=list)
    characteristics: List[Characteristic] = field(default_factory=list)  # NEW
    compu_methods: List[CompuMethod] = field(default_factory=list)
    compu_vtabs: List[CompuVTab] = field(default_factory=list)
    record_layouts: List[RecordLayout] = field(default_factory=list)
    groups: List[Group] = field(default_factory=list)
    functions: List[Function] = field(default_factory=list)

    raw_blocks: List[A2LBlock] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        def conv(obj):
            if hasattr(obj, "__dict__"):
                return asdict(obj)
            if isinstance(obj, list):
                return [conv(x) for x in obj]
            return obj
        return conv(self)


# --------------------------
# Parsing helpers for known blocks
# --------------------------

def parse_protocol_layer(block: A2LBlock) -> ProtocolLayer:
    pl = ProtocolLayer(raw=block.lines[:])
    tokens = []
    for ln in block.lines:
        t = tokenize_line(ln)
        if not t:
            continue
        tokens.append(t)

    flat = [tok for line in tokens for tok in line]

    idx = 0
    if idx < len(flat):
        v = to_int(flat[idx])
        if v is not None:
            pl.version = v
            idx += 1

    while idx < len(flat):
        tok = flat[idx]
        if tok.startswith("BYTE_ORDER") or tok.startswith("ADDRESS_GRANULARITY") or tok == "OPTIONAL_CMD" or tok == "COMMUNICATION_MODE_SUPPORTED":
            break
        val = to_int(tok)
        if val is not None:
            pl.timing_values.append(val)
            idx += 1
            continue
        else:
            idx += 1
            break

    for i, tok in enumerate(flat):
        if tok.startswith("BYTE_ORDER"):
            pl.byte_order = tok
        elif tok.startswith("ADDRESS_GRANULARITY"):
            pl.address_granularity = tok
        elif tok == "OPTIONAL_CMD" and i + 1 < len(flat):
            pl.optional_cmds.append(flat[i + 1])
        elif tok == "COMMUNICATION_MODE_SUPPORTED" and i + 1 < len(flat):
            pl.communication_mode = flat[i + 1]
        elif tok == "MASTER":
            if i + 2 < len(flat):
                pl.master_max_bs = to_int(flat[i + 1])
                pl.master_min_st = to_int(flat[i + 2])

    before_enum = []
    for tok in flat:
        if tok.startswith("BYTE_ORDER") or tok.startswith("ADDRESS_GRANULARITY"):
            break
        v = to_int(tok)
        if v is not None:
            before_enum.append(v)
    if len(before_enum) >= 3:
        pl.max_cto = before_enum[-3]
        pl.max_dto = before_enum[-2]

    return pl

def parse_daq(block: A2LBlock) -> DaqConfig:
    dq = DaqConfig(raw=block.lines[:])
    lines = block.lines[:]

    toks = []
    for ln in lines:
        t = tokenize_line(ln)
        if t:
            toks.append(t)

    flat = [x for line in toks for x in line]

    if flat:
        dq.mode = flat[0] if flat[0] in ("STATIC", "DYNAMIC") else None

    nums = [to_int(x) for x in flat[1:1 + 3]]
    if len(nums) >= 3:
        dq.max_daq, dq.max_event_channel, dq.min_daq = nums[:3]

    for i, tok in enumerate(flat):
        if tok.startswith("IDENTIFICATION_FIELD_TYPE_"):
            dq.identification_field_type = tok
        elif tok.startswith("GRANULARITY_ODT_ENTRY_SIZE_DAQ_") or tok.startswith("GRANULARITY_ODT_ENTRY_SIZE_DAQ"):
            dq.odt_entry_granularity_daq = tok
        elif tok == "OVERLOAD_INDICATION_EVENT":
            dq.overload_indication = "EVENT"
        elif tok.startswith("GRANULARITY_ODT_ENTRY_SIZE_STIM_"):
            dq.stim_granularity = tok
        elif tok == "BIT_STIM_SUPPORTED":
            dq.bit_stim_supported = True

    for i, tok in enumerate(flat):
        if tok.startswith("GRANULARITY_ODT_ENTRY_SIZE_DAQ"):
            if i + 1 < len(flat):
                dq.max_odt_entry_size_daq = to_int(flat[i + 1])
        if tok.startswith("GRANULARITY_ODT_ENTRY_SIZE_STIM"):
            if i + 1 < len(flat):
                dq.max_odt_entry_size_stim = to_int(flat[i + 1])

    for evb in block.get_children("EVENT"):
        dq.events.append(parse_daq_event(evb))

    return dq

def parse_daq_event(block: A2LBlock) -> DaqEvent:
    lines = [ln for ln in block.lines if ln.strip()]
    toks = [tokenize_line(ln) for ln in lines]
    flat = [x for line in toks for x in line]

    quoted = [unquote(x) for x in flat if (x.startswith('"') and x.endswith('"'))]
    name = quoted[0] if quoted else ""
    short = quoted[1] if len(quoted) > 1 else None

    nums = [to_int(x) for x in flat if to_int(x) is not None]
    evt_num = nums[0] if nums else None

    type_tok = None
    for x in flat:
        if x in ("DAQ", "STIM", "DAQ_STIM"):
            type_tok = x
            break

    cycle = time_unit = priority = None
    max_daq_list = None
    try:
        ti = flat.index(type_tok)
        seq = []
        for x in flat[ti+1:]:
            if to_int(x) is not None:
                seq.append(to_int(x))
        if len(seq) >= 4:
            max_daq_list, cycle, time_unit, priority = seq[:4]
    except Exception:
        pass

    return DaqEvent(
        name=name,
        short_name=short,
        event_channel_number=evt_num,
        type=type_tok,
        max_daq_list=max_daq_list,
        cycle=cycle,
        time_unit=time_unit,
        priority=priority,
        raw=block.lines[:]
    )

def parse_xcp_on_can(block: A2LBlock) -> XcpOnCanConfig:
    xcp = XcpOnCanConfig(raw=block.lines[:])
    lines = block.lines[:]

    toks = [tokenize_line(ln) for ln in lines if ln.strip()]
    flat = [x for line in toks for x in line]
    if flat and to_int(flat[0]) is not None:
        xcp.version = to_int(flat[0])

    kv_re = re.compile(r"^([A-Z0-9_]+)\s+(\S+)$")
    for ln in lines:
        s = ln.strip()
        m = kv_re.match(s)
        if not m:
            continue
        key, value = m.group(1), m.group(2)
        key_u = key.upper()
        if key_u == "CAN_ID_BROADCAST":
            xcp.can_id_broadcast = to_int(value)
        elif key_u == "CAN_ID_MASTER":
            xcp.can_id_master = to_int(value)
        elif key_u == "CAN_ID_SLAVE":
            xcp.can_id_slave = to_int(value)
        elif key_u == "CAN_ID_GET_DAQ_CLOCK_MULTICAST":
            xcp.can_id_get_daq_clock_multicast = to_int(value)
        elif key_u == "BAUDRATE":
            xcp.baudrate = to_int(value)
        elif key_u == "SAMPLE_POINT":
            xcp.sample_point = to_int(value)
        elif key_u == "SAMPLE_RATE":
            xcp.sample_rate = value
        elif key_u == "BTL_CYCLES":
            xcp.btl_cycles = to_int(value)
        elif key_u == "SJW":
            xcp.sjw = to_int(value)
        elif key_u == "SYNC_EDGE":
            xcp.sync_edge = value
        elif key_u == "MAX_DLC_REQUIRED":
            xcp.max_dlc_required = True
        elif key_u == "MAX_BUS_LOAD":
            xcp.max_bus_load = to_int(value)

    fd_block = block.get_first_child("CAN_FD")
    if fd_block:
        xcp.can_fd = parse_can_fd(fd_block)
    return xcp

def parse_can_fd(block: A2LBlock) -> XcpOnCanFdConfig:
    fd = XcpOnCanFdConfig(raw=block.lines[:])
    kv_re = re.compile(r"^([A-Z0-9_]+)\s+(\S+)$")
    for ln in block.lines:
        s = ln.strip()
        m = kv_re.match(s)
        if not m:
            continue
        key, value = m.group(1), m.group(2)
        ku = key.upper()
        if ku == "MAX_DLC":
            fd.max_dlc = to_int(value)
        elif ku == "CAN_FD_DATA_TRANSFER_BAUDRATE":
            fd.data_transfer_baudrate = to_int(value)
        elif ku == "SAMPLE_POINT":
            fd.sample_point = to_int(value)
        elif ku == "BTL_CYCLES":
            fd.btl_cycles = to_int(value)
        elif ku == "SJW":
            fd.sjw = to_int(value)
        elif ku == "SYNC_EDGE":
            fd.sync_edge = value
        elif ku == "MAX_DLC_REQUIRED":
            fd.max_dlc_required = True
        elif ku == "SECONDARY_SAMPLE_POINT":
            fd.secondary_sample_point = to_int(value)
        elif ku == "TRANSCEIVER_DELAY_COMPENSATION":
            fd.tdc = value
    return fd

def parse_segment_info(seg_block: A2LBlock) -> SegmentInfo:
    si = SegmentInfo(raw=seg_block.lines[:])
    toks = [tokenize_line(ln) for ln in seg_block.lines if ln.strip()]
    flat = [x for line in toks for x in line]
    nums = [to_int(x) for x in flat if to_int(x) is not None]
    if len(nums) >= 5:
        si.segment_number, si.num_pages, si.address_extension, si.compression_method, si.encryption_method = nums[:5]
    cs = seg_block.get_first_child("CHECKSUM")
    if cs:
        for ln in cs.lines:
            t = tokenize_line(ln)
            if t:
                si.checksum_type = t[0]
                break
    for pg in seg_block.get_children("PAGE"):
        page_tokens = [tokenize_line(ln) for ln in pg.lines if ln.strip()]
        flatp = [x for ln in page_tokens for x in ln]
        pn = to_int(flatp[0]) if flatp else None
        ecu_acc = flatp[1] if len(flatp) > 1 else None
        xcp_rd = flatp[2] if len(flatp) > 2 else None
        xcp_wr = flatp[3] if len(flatp) > 3 else None
        si.pages.append(PageInfo(page_number=pn, ecu_access=ecu_acc, xcp_read_access=xcp_rd, xcp_write_access=xcp_wr))
    return si

def parse_memory_segment(block: A2LBlock) -> MemorySegment:
    name = block.args[0] if block.args else ""
    long_id = None
    if len(block.args) > 1:
        long_id = unquote(" ".join(block.args[1:])) if block.args[1:] else None

    class_type = None
    memory_type = None
    address = None
    size = None
    attrs: List[str] = []

    for ln in block.lines:
        s = ln.strip()
        if not s:
            continue
        if class_type is None and memory_type is None:
            tt = tokenize_line(s)
            if len(tt) == 2 and tt[0].isalpha() and tt[1].isalpha():
                class_type, memory_type = tt[0], tt[1]
                continue
        parts = tokenize_line(s)
        if parts and (parts[0] in ("INTERN", "EXTERN")) and address is None:
            if len(parts) >= 3:
                address = to_int(parts[1])
                size = to_int(parts[2])
                if len(parts) > 3:
                    attrs = parts[3:]
                continue

    seg_info = None
    if_data = block.get_first_child("IF_DATA")
    if if_data:
        xcpp = if_data.get_first_child("XCPplus")
        if xcpp:
            segblk = xcpp.get_first_child("SEGMENT")
            if segblk:
                seg_info = parse_segment_info(segblk)

    return MemorySegment(
        name=name,
        long_identifier=long_id,
        class_type=class_type,
        memory_type=memory_type,
        address=address,
        size=size,
        attributes=attrs,
        segment_info=seg_info,
        raw=block.lines[:]
    )
def parse_axis_pts(block: A2LBlock) -> AxisPts:
    # Name can be in /begin line args or as the first line inside the block
    lines = [ln for ln in block.lines if ln.strip()]
    i = 0

    if block.args and len(block.args) > 0:
        name = block.args[0]
    else:
        # First non-empty line is the name
        first = tokenize_line(lines[i]) if i < len(lines) else []
        name = first[0] if first else ""
        i += 1

    def next_token_line():
        nonlocal i
        while i < len(lines):
            t = tokenize_line(lines[i])
            i += 1
            if t:
                return t
        return []

    # Description
    desc_tokens = next_token_line()
    description = unquote(" ".join(desc_tokens)) if desc_tokens else ""

    # Address
    addr = None
    t = next_token_line()
    if t:
        addr = to_int(t[0])

    input_qty = None
    t = next_token_line()
    if t:
        input_qty = t[0]

    record_layout = None
    t = next_token_line()
    if t:
        record_layout = t[0]

    deposit = None
    t = next_token_line()
    if t:
        deposit = to_int(t[0])

    compu_method = None
    t = next_token_line()
    if t:
        compu_method = t[0]

    max_points = None
    t = next_token_line()
    if t:
        max_points = to_int(t[0])

    lower = upper = None
    t = next_token_line()
    if t:
        lower = to_float(t[0]) if to_float(t[0]) is not None else to_int(t[0])
    t = next_token_line()
    if t:
        upper = to_float(t[0]) if to_float(t[0]) is not None else to_int(t[0])

    # Optional: BYTE_ORDER, FORMAT, IF_DATA, SYMBOL_LINK, etc.
    byte_order = None
    fmt = None
    symbol_link = None

    for ln in lines[i:]:
        tt = tokenize_line(ln)
        if not tt:
            continue
        if tt[0].upper() == "BYTE_ORDER":
            if len(tt) > 1:
                byte_order = tt[1]
        elif tt[0].upper() == "FORMAT":
            if len(tt) > 1:
                fmt = tt[1]
        elif tt[0].upper() == "SYMBOL_LINK":
            # SYMBOL_LINK "name" index
            if len(tt) >= 3:
                symbol_link = (unquote(tt[1]), to_int(tt[2]) or 0)

    return AxisPts(
        name=name,
        description=description,
        address=addr,
        input_quantity=input_qty,
        record_layout=record_layout,
        deposit=deposit,
        compu_method=compu_method,
        max_axis_points=max_points,
        lower_limit=lower,
        upper_limit=upper,
        byte_order=byte_order,
        format_str=fmt,
        symbol_link=symbol_link,
        raw=block.lines[:]
    )


def parse_measurement(block: A2LBlock) -> Measurement:
    # Name can be in /begin args or first line inside the block
    lines = [ln for ln in block.lines if ln.strip()]
    i = 0

    if block.args and len(block.args) > 0:
        name = block.args[0]
    else:
        t0 = tokenize_line(lines[i]) if i < len(lines) else []
        name = t0[0] if t0 else ""
        i += 1  # advance past the name line

    def next_tokens():
        nonlocal i
        while i < len(lines):
            t = tokenize_line(lines[i])
            i += 1
            if t:
                return t
        return []

    desc = unquote(" ".join(next_tokens())) if i < len(lines) else ""
    datatype = next_tokens()[0] if i < len(lines) else ""
    compu_method = next_tokens()[0] if i < len(lines) else ""

    params: List[str] = []
    ecu_address = None
    address = None
    lower = None
    upper = None
    symbol_link = None

    while i < len(lines):
        t = tokenize_line(lines[i])
        i += 1
        if not t:
            continue
        key = t[0].upper()
        if key in ("ECU_ADDRESS", "ADDRESS"):
            if len(t) > 1:
                val = to_int(t[1])
                if key == "ECU_ADDRESS":
                    ecu_address = val
                else:
                    address = val
        elif key == "SYMBOL_LINK":
            if len(t) >= 3:
                symbol_link = (unquote(t[1]), to_int(t[2]) or 0)
        else:
            # numeric params, limits, or other tokens
            if len(t) == 1 and (to_int(t[0]) is not None or to_float(t[0]) is not None):
                params.append(t[0])
            elif len(t) == 2 and all([(to_float(x) is not None or to_int(x) is not None) for x in t]):
                lower = to_float(t[0]) if to_float(t[0]) is not None else to_int(t[0])
                upper = to_float(t[1]) if to_float(t[1]) is not None else to_int(t[1])
            else:
                params.extend(t)

    return Measurement(
        name=name,
        description=desc,
        datatype=datatype,
        compu_method=compu_method,
        params=params,
        ecu_address=ecu_address,
        address=address,
        lower_limit=lower,
        upper_limit=upper,
        symbol_link=symbol_link,
        raw=block.lines[:]
    )


def parse_characteristic(block: A2LBlock) -> Characteristic:
    """
    CHARACTERISTIC name on first content line when absent from /begin.
    Then:
      "<desc>"
      <type>
      <address>
      <record_layout>
      <max_diff>
      <compu_method>
      <lower>
      <upper>
    Optional SYMBOL_LINK lines may follow.
    """
    lines = [ln for ln in block.lines if ln.strip()]
    i = 0

    if block.args and len(block.args) > 0:
        name = block.args[0]
    else:
        t0 = tokenize_line(lines[i]) if i < len(lines) else []
        name = t0[0] if t0 else ""
        i += 1  # advance past name

    def next_tokens():
        nonlocal i
        while i < len(lines):
            t = tokenize_line(lines[i])
            i += 1
            if t:
                return t
        return []

    desc = unquote(" ".join(next_tokens())) if i < len(lines) else ""
    char_type = next_tokens()[0] if i < len(lines) else ""

    addr = None
    t = next_tokens()
    if t:
        addr = to_int(t[0])

    record_layout = None
    t = next_tokens()
    if t:
        record_layout = t[0]

    max_diff = None
    t = next_tokens()
    if t:
        max_diff = to_float(t[0]) if to_float(t[0]) is not None else to_int(t[0])

    compu_method = None
    t = next_tokens()
    if t:
        compu_method = t[0]

    lower = upper = None
    t = next_tokens()
    if t:
        lower = to_float(t[0]) if to_float(t[0]) is not None else to_int(t[0])
    t = next_tokens()
    if t:
        upper = to_float(t[0]) if to_float(t[0]) is not None else to_int(t[0])

    symbol_link = None
    for ln in lines[i:]:
        tt = tokenize_line(ln)
        if not tt:
            continue
        if tt[0].upper() == "SYMBOL_LINK" and len(tt) >= 3:
            symbol_link = (unquote(tt[1]), to_int(tt[2]) or 0)

    return Characteristic(
        name=name,
        description=desc,
        char_type=char_type,
        address=addr,
        record_layout=record_layout,
        max_diff=max_diff,
        compu_method=compu_method,
        lower_limit=lower,
        upper_limit=upper,
        symbol_link=symbol_link,
        raw=block.lines[:]
    )

def parse_compu_method(block: A2LBlock) -> CompuMethod:
    name = block.args[0] if block.args else ""
    lines = [ln for ln in block.lines if ln.strip()]
    i = 0
    def next_tokens():
        nonlocal i
        while i < len(lines):
            t = tokenize_line(lines[i])
            i += 1
            if t:
                return t
        return []

    desc = unquote(" ".join(next_tokens())) if lines else ""
    method_type = next_tokens()[0] if lines else ""
    fmt = unquote(" ".join(next_tokens())) if lines else None
    unit = unquote(" ".join(next_tokens())) if lines else None
    coeffs: List[float] = []
    for ln in lines[i:]:
        tt = tokenize_line(ln)
        if not tt:
            continue
        if tt[0].upper() == "COEFFS":
            for v in tt[1:]:
                if to_float(v) is not None:
                    coeffs.append(float(v))
    return CompuMethod(name=name, description=desc, method_type=method_type, format_str=fmt, unit=unit, coeffs=coeffs, raw=block.lines[:])

def parse_compu_vtab(block: A2LBlock) -> CompuVTab:
    name = block.args[0] if block.args else ""
    lines = [ln for ln in block.lines if ln.strip()]
    i = 0
    def next_tokens():
        nonlocal i
        while i < len(lines):
            t = tokenize_line(lines[i])
            i += 1
            if t:
                return t
        return []

    desc = unquote(" ".join(next_tokens())) if lines else ""
    tab_type = next_tokens()[0] if lines else ""
    entries: List[Tuple[int, str]] = []
    count = None
    t = next_tokens()
    if t and to_int(t[0]) is not None:
        count = to_int(t[0])
        for _ in range(count or 0):
            tt = next_tokens()
            if not tt:
                continue
            val = to_int(tt[0])
            verb = unquote(" ".join(tt[1:])) if len(tt) > 1 else ""
            if val is not None:
                entries.append((val, verb.strip('"')))
    else:
        while True:
            tt = next_tokens()
            if not tt:
                break
            try:
                val = to_int(tt[0])
                verb = unquote(" ".join(tt[1:]))
                if val is not None:
                    entries.append((val, verb))
            except Exception:
                break

    return CompuVTab(name=name, description=desc, tab_type=tab_type, entries=entries, raw=block.lines[:])

def parse_record_layout(block: A2LBlock) -> RecordLayout:
    name = block.args[0] if block.args else ""
    entries = [ln.strip() for ln in block.lines if ln.strip()]
    return RecordLayout(name=name, entries=entries, raw=block.lines[:])

def parse_group(block: A2LBlock) -> Group:
    name = block.args[0] if block.args else ""
    lines = [ln for ln in block.lines if ln.strip()]
    desc = ""
    refs: List[str] = []
    if lines:
        t = tokenize_line(lines[0])
        if t:
            desc = unquote(" ".join(t))
    for rb in block.get_children("REF_MEASUREMENT"):
        for ln in rb.lines:
            t = tokenize_line(ln)
            for tok in t:
                if tok not in ("/begin", "/end"):
                    refs.append(tok)
    return Group(name=name, description=desc, ref_measurements=refs, raw=block.lines[:])

def parse_function(block: A2LBlock) -> Function:
    name = block.args[0] if block.args else ""
    lines = [ln for ln in block.lines if ln.strip()]
    desc = ""
    loc: List[str] = []
    if lines:
        t = tokenize_line(lines[0])
        if t:
            desc = unquote(" ".join(t))
    for lb in block.get_children("LOC_MEASUREMENT"):
        for ln in lb.lines:
            t = tokenize_line(ln)
            for tok in t:
                loc.append(tok)
    loc = [x for x in loc if x not in ("/begin", "/end")]
    return Function(name=name, description=desc, loc_measurements=loc, raw=block.lines[:])


# --------------------------
# A2L file block parser (generic tree)
# --------------------------

class BlockBuilder:
    def __init__(self):
        self.root = A2LBlock(name="ROOT", args=[])
        self.stack = [self.root]

    def feed_line(self, line: str):
        s = line.strip()
        if not s:
            return
        if s.lower().startswith("/begin"):
            m = re.match(r"/begin\s+(\S+)\s*(.*)$", s, flags=re.I)
            if not m:
                self.stack[-1].lines.append(line.rstrip("\n"))
                return
            name = m.group(1)
            if name == "MEASUREMENT":
                pass
            args_str = m.group(2).strip()
            args = []
            if args_str:
                try:
                    args = shlex.split(args_str, posix=True)
                except Exception:
                    args = args_str.split()
            blk = A2LBlock(name=name, args=args, lines=[], children=[])
            self.stack[-1].children.append(blk)
            self.stack.append(blk)
        elif s.lower().startswith("/end"):
            if len(self.stack) > 1:
                self.stack.pop()
        else:
            self.stack[-1].lines.append(line.rstrip("\n"))

    def get_root(self) -> A2LBlock:
        return self.root


# --------------------------
# Top-level parser
# --------------------------

class A2LParser:
    def parse_file(self, path: str | Path) -> A2LModel:
        text = Path(path).read_text(encoding="utf-8", errors="ignore")
        return self.parse_text(text)

    def parse_text(self, text: str) -> A2LModel:
        cleaned = strip_block_comments(text)
        bb = BlockBuilder()
        for ln in cleaned.splitlines():
            bb.feed_line(ln)
        root = bb.get_root()

        model = A2LModel(raw_blocks=[root])

        proj = root.get_first_child("PROJECT")
        if proj:
            if proj.args:
                model.project_name = proj.args[0]
            mod = proj.get_first_child("MODULE")
            if mod and mod.args:
                model.module_name = mod.args[0]

            if mod:
                for ifd in mod.get_children("IF_DATA"):
                    if ifd.args and ifd.args[0] == "XCPplus":
                        pl = ifd.get_first_child("PROTOCOL_LAYER")
                        if pl:
                            model.protocol_layer = parse_protocol_layer(pl)

                        dq = ifd.get_first_child("DAQ")
                        if dq:
                            model.daq = parse_daq(dq)
                            model.daq_events = list(model.daq.events)

                        xcp_can = ifd.get_first_child("XCP_ON_CAN")
                        if xcp_can:
                            model.xcp_on_can = parse_xcp_on_can(xcp_can)

                mod_par = mod.get_first_child("MOD_PAR")
                if mod_par:
                    for ms in mod_par.get_children("MEMORY_SEGMENT"):
                        model.memory_segments.append(parse_memory_segment(ms))

                for ax in mod.get_children("AXIS_PTS"):
                    model.axis_pts.append(parse_axis_pts(ax))

                for meas in mod.get_children("MEASUREMENT"):
                    model.measurements.append(parse_measurement(meas))

                # NEW: CHARACTERISTIC
                for ch in mod.get_children("CHARACTERISTIC"):
                    model.characteristics.append(parse_characteristic(ch))

                for cm in mod.get_children("COMPU_METHOD"):
                    model.compu_methods.append(parse_compu_method(cm))

                for cv in mod.get_children("COMPU_VTAB"):
                    model.compu_vtabs.append(parse_compu_vtab(cv))

                for rl in mod.get_children("RECORD_LAYOUT"):
                    model.record_layouts.append(parse_record_layout(rl))

                for grp in mod.get_children("GROUP"):
                    model.groups.append(parse_group(grp))

                for fn in mod.get_children("FUNCTION"):
                    model.functions.append(parse_function(fn))

        return model


# --------------------------
# CLI helper (optional)
# --------------------------

def main():

    parser = A2LParser()
    model = parser.parse_file("D902_00_VW_P_V00_C00_W1_DA_SFW_LUK.a2l")
    print(f"Project: {model.project_name} | Module: {model.module_name}")
    print(f"Protocol Layer parsed: {model.protocol_layer is not None}")
    print(f"DAQ events: {len(model.daq_events)}")
    print(f"XCP on CAN parsed: {model.xcp_on_can is not None}")
    print(f"Memory segments: {len(model.memory_segments)}")
    print(f"AXIS_PTS: {len(model.axis_pts)}")
    print(f"Measurements: {len(model.measurements)}")
    print(f"Characteristics: {len(model.characteristics)}")  # NEW
    print(f"Record layouts: {len(model.record_layouts)}")
    if model.characteristics:
        c = model.characteristics[0]
        print("First CHARACTERISTIC:", c.name, c.char_type, hex(c.address or 0), c.record_layout, c.compu_method)
    if model.daq_events:
        print("First DAQ event:", model.daq_events[0])
    if model.axis_pts:
        print("First AXIS_PTS:", model.axis_pts[0].name, hex(model.axis_pts[0].address or 0))


if __name__ == "__main__":
    main()