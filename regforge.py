#!/usr/bin/env python3
#############################################################################################################
##   _______   _                      __     __             _    
##  / ___/ /  (_)__  __ _  __ _____  / /__  / /  ___  ___ _(_)___ TM
## / /__/ _ \/ / _ \/  ' \/ // / _ \/  '_/ / /__/ _ \/ _ `/ / __/          ////  O P E N - S O U R C E ////
## \___/_//_/_/ .__/_/_/_/\_,_/_//_/_/\_\ /____/\___/\_, /_/\__/ 
##           /_/                                    /___/              
#############################################################################################################
# Tool             : RegForge
# Developer        : Mitu Raj, chip@chipmunklogic.com
#                    Chipmunk Logic™, https://chipmunklogic.com
#
# Description      : RegForge is a simple tool that generates APB register blocks for your RTL designs. 
#                    The input is a plain text file (regfile) that describes registers with access rules.
#                    The output is the register block in RTL (described in SV) with APB interface.
#
# Last modified on : May-2026
# Compatiblility   : Python 3.9 tested
# Notes            : Usage- regforge.py <regfile>
#                    eg: regforge.py uart_regs.txt
#                        Dumps output file = uart_regs_apb_top.sv
#
# Documentation    : https://github.com/iammituraj/RegForge/blob/main/README.md
#
# Copyright        : Open-source license, see LICENSE.
#############################################################################################################

#### Libraries ####
import sys
import os
from datetime import datetime;
#timestr = f"Run time: {datetime.now():%Y-%m-%d %H:%M:%S}"

#### User-defined Functions ####
# Display usage syntax
def usage():
    print("Usage:")
    print("  regforge.py <regfile>")
    print("")
    print("Example:")
    print("  regforge.py myregs")

# Verify regfile structure
def verify_regfile_struct(infile):
    # Global vars
    global addr_width
    global addr_width_hexdigits
    global end_addr
    global max_reg_addr
    global max_regs
    global reg_cnt
    global mdlname
    global outfile
    
    # Local vars
    start_addrspace_cnt = 0
    start_regs_cnt = 0
    is_addrspace_present = False
    is_regs_present = False
    is_atleast_one_reg_present = False
    is_addr_width_present = False
    is_mdlname_present = False

    # Analyze line-by-line
    with open(infile, "r") as f:
        for lineno, line in enumerate(f, start=1):
            line = line.strip().lower()

            # Ignore blank lines
            if not line:
                continue

            # Ignore comment lines
            if line.startswith("//"):
                continue

            # Look for labels START_ADDRSPACE and START_REGS
            if line == "#start_addrspace":
                start_addrspace_cnt += 1
                if is_addrspace_present:
                    break
                is_addrspace_present = True
            elif line == "#start_regs":
                start_regs_cnt += 1
                if is_regs_present:
                    break
                is_regs_present = True
                if not is_addrspace_present:
                    print(f"ERROR (line {lineno}): #START_ADDRSPACE must appear before #START_REGS")
                    sys.exit(1)

            # Verify if the mandatory global params are present           
            if is_addrspace_present and not is_regs_present:
                 if "=" in line:
                    param, val = [x.strip() for x in line.split("=", 1)]
                    # Parse addr_width and validate
                    if param == "addr_width":
                        is_addr_width_present = True    
                        try:
                            w = int(val)
                            if w <= 0:
                                raise ValueError
                            addr_width = w
                            addr_width_hexdigits = (addr_width + 3) // 4
                            if not (MIN_ADDR_WIDTH <= addr_width <= MAX_ADDR_WIDTH):
                                print(f"ERROR (line {lineno}): addr_width must be in the range [2, 32]")
                                sys.exit(1)

                            # Calculate address space boundaries
                            end_addr = ((1 << addr_width) - 1)
                            max_reg_addr = ((1 << addr_width) - 1) + 1 - REG_SIZE_IN_BYTES
                            max_regs = 1 << addr_width

                        except ValueError:
                            print("ERROR: addr_width must be in the range [2, 32]")
                            sys.exit(1)
                    # Parse mdlname
                    if param == "mdlname":
                        is_mdlname_present = True  
                        mdlname = val  
                        outfile = val + ".sv"
                        DEBUG_MODE and print(f"Output file = {outfile}\n")
            
            # Verify if atleast one register is present
            if is_addrspace_present and is_regs_present:
                if "=" in line:
                    param, val = [x.strip() for x in line.split("=", 1)]
                    if param == "reg" and val:
                        is_atleast_one_reg_present = True
                        reg_cnt += 1
    
    # Verify the regfile skeltal structure
    # 1. Labels START_ADDRSPACE, START_REGS defined?
    # 2. addr_width, mdlname params defined?
    # 3. Atleast one register defined?
    # 4. Register count must be within the address space boundaries
    if start_addrspace_cnt != 1:
        print("ERROR: File must contain exactly one #START_ADDRSPACE label")
        sys.exit(1)
    if start_regs_cnt != 1:
        print("ERROR: File must contain exactly one #START_REGS label")
        sys.exit(1)
    if not is_addr_width_present:
        print("ERROR: File missing the mandatory parameter 'addr_width'")
        sys.exit(1)
    if not is_mdlname_present:
        print("ERROR: File missing the mandatory parameter 'mdlname'")
        sys.exit(1)
    if not is_atleast_one_reg_present :
        print("ERROR: File has no registers, atleast one register must be defined")
        sys.exit(1)
    if reg_cnt > max_regs:
        print(f"ERROR: addr_width is not sufficient to support {regcnt} registers in the defined address space")
        sys.exit(1)

# Validate idx and store to DB
def validate_idx(val, curr_reg, curr_field, lineno):
    # Global vars
    global reg_db

    idxvalue = val

    # Validate [x:y] format
    if not (val.startswith("[") and val.endswith("]")):
        print(f"ERROR (line {lineno}): idx must be in format [x:y]")
        sys.exit(1)
    try:
        x_str, y_str = [t.strip() for t in val[1:-1].split(":", 1)]
    except ValueError:
        print(f"ERROR (line {lineno}): idx must be in format [x:y]")
        sys.exit(1)

    # Validate x, y to be >=0 and integers
    if not (x_str.isdigit() and y_str.isdigit()):
        print(f"ERROR (line {lineno}): idx must be in format [x:y] and idx values must be non-negative integers")
        sys.exit(1)
    
    # Convert to integers
    x = int(x_str)
    y = int(y_str)

    # Check 0 <= y <= x < REG_WIDTH
    if x < y or y < 0 or x >= REG_WIDTH:
        print(f"ERROR (line {lineno}): idx must satisfy 0 <= y <= x < {REG_WIDTH}")
        sys.exit(1)

    # Compute field width
    field_width = x - y + 1

    # Store idx, width to DB
    reg_db[curr_reg]["fields"][curr_field]["idx"] = idxvalue
    reg_db[curr_reg]["fields"][curr_field]["width"] = field_width


# Validate rstval and store to DB
def validate_rstval(val, curr_reg, curr_field, lineno):
    # Global vars
    global reg_db

    rstvalue = val

    # Allow NA; means no reset required
    if rstvalue == "na":
        reg_db[curr_reg]["fields"][curr_field]["rstval"] = "na"
        return

    # Must be in 0x format
    if not rstvalue.startswith("0x"):
        print(f"ERROR (line {lineno}): rstval must be specified in 0x format")
        sys.exit(1)

    # Get the current field width
    field_width = int(reg_db[curr_reg]["fields"][curr_field]["width"])

    # Check if value fits in width
    try:
        rstvalue_int = int(rstvalue, 16)
    except ValueError:
        print(f"ERROR (line {lineno}): Invalid rstval '{val}'")
        sys.exit(1)
    if rstvalue_int >= (1 << field_width):
        print(f"ERROR (line {lineno}): rstval '{val}' does not fit in the field {curr_field} of {field_width} bits")
        sys.exit(1)

    # Store rstval to DB in size'h<value> format
    reg_db[curr_reg]["fields"][curr_field]["rstval"] = f"{field_width}'h{rstvalue_int:x}"

# =============================================================================
# Create register database
# =============================================================================
# REGISTER DATABASE STRUCTURE (reg_db)
#
# reg_db
# ├── <reg_name>                          # Example: "uart_intr_en"
# │   ├── offset      : int               # Register offset from base address
# │   ├── lineno      : int               # Line number of reg in regfile
# │   ├── desc        : str               # Register description
# │   ├── bitmap      : str               # Register bit map
# │   │
# │   └── fields                          # Dictionary of fields in the register
# │       ├── <field_name>                # Example: "tx_ready"
# │       │   ├── idx         : int       # Starting bit index of field
# │       │   ├── width       : int       # Field width in bits
# │       │   ├── swacc       : str       # Software access type
# │       │   ├── hwacc       : str       # Hardware access type
# │       │   ├── rstval      : str       # Reset value (example: "1'h0")
# │       │   ├── desc        : str       # Field description
# │       │   └── lineno      : int       # Line number of field in regfile
# │       │   └── hwctl       : str       # HW control
# │       │   └── swevt       : str       # SW event
# │       │   └── impl        : str       # Implementation in Hardware
# │       │   └── in_ports    : str arr   # Associated input ports
# │       │   └── in_ports_w  : int arr   # Input ports width
# │       │   └── out_ports   : str arr   # Associated output ports
# │       │   └── out_ports_w : int arr   # Output ports width
# │       │
# │       └── <field_name>
# │           └── ...
# │
# └── <reg_name>
#     └── ...
# =============================================================================
def create_regdb(infile):
    # Global vars
    global reg_db

    # Local vars
    curr_reg = None
    curr_field = None
    curr_offset = base_addr
    is_regs_section = False

    # Analyze line-by-line
    with open(infile, "r") as f:
        for lineno, line in enumerate(f, start=1):
            lineraw = line.strip() 
            line = lineraw.lower()

            # Ignore blank lines
            if not line:
                continue

            # Ignore comment lines
            if line.startswith("//"):
                continue
            
            # Look for START_REGs label to start parsing REG PARAMs
            if line == "#start_regs":
                is_regs_section = True
                continue

            # Ignore content before START_REGS...
            if not is_regs_section: 
                continue

            # Ignore junk...
            if "=" not in line:
                continue
            
            ## Parse reg/field params and validate ##
            param, val = [x.strip() for x in line.split("=", 1)]
            raw_param, raw_val = [x.strip() for x in lineraw.split("=", 1)]

            # Valid param?
            if param not in VALID_REG_PARAMS:
                print(f"ERROR (line {lineno}): Invalid reg/field parameter '{param}'")
                sys.exit(1)

            # Validate register and store to DB
            if param == "reg":
                if not val:
                    print(f"ERROR (line {lineno}): Param 'reg' cannot be empty")
                    sys.exit(1)

                # Check for duplicate register
                if raw_val in reg_db:
                    print(f"ERROR (line {lineno}): Register '{raw_val}' defined multiple times")
                    sys.exit(1)
                
                # Store the register to DB
                curr_field = None 
                curr_reg = raw_val
                reg_db[curr_reg] = {"lineno":lineno, "fields":{}}
                continue

            # Validate field within the register and store to DB
            elif curr_reg is not None and param == "field":
                if not val:
                    print(f"ERROR (line {lineno}): Param 'field' cannot be empty")
                    sys.exit(1)

                # Check for duplicate fields
                if raw_val in reg_db[curr_reg]["fields"]:
                    print(f"ERROR (line {lineno}): Field '{raw_val}' defined multiple times within the register {curr_reg}")
                    sys.exit(1)

                ## Verify register completeness ##
                # Before parsing the first field of the current register, the register's offset, desc must be populated with default if missing...
                if curr_field is None:

                    # Add current offset
                    if "offset" not in reg_db[curr_reg]:
                        # Validate the current offset if within the addr range
                        if curr_offset > max_reg_addr:
                            print(f"ERROR: offset {hex(curr_offset)} of the register {curr_reg} exceeds max register address {hex(max_reg_addr)}")
                            sys.exit(1)

                        # Store current offset to DB and increment the offset
                        reg_db[curr_reg]["offset"] = curr_offset
                        curr_offset += OFFSET_PER_REG

                    # Add default desc, if not provided, and store to DB
                    if "desc" not in reg_db[curr_reg]:
                        reg_db[curr_reg]["desc"] = DEFAULT_DESC
                
                # Store the field to DB
                curr_field = raw_val
                reg_db[curr_reg]["fields"][curr_field] = {"lineno":lineno}
                continue

            # Validate offset within the register and store to DB
            elif curr_reg is not None and curr_field is None and param == "offset":
                if not val:
                    print(f"ERROR (line {lineno}): Param 'offset' cannot be empty")
                    sys.exit(1)

                # Check for duplicate offset
                if param in reg_db[curr_reg]:
                    print(f"ERROR (line {lineno}): Param 'offset' defined multiple times within the register {curr_reg}")
                    sys.exit(1)

                # Check if Hex format
                if not val.startswith("0x"):
                    print(f"ERROR (line {lineno}): offset must be specified in hex (0x...)")
                    sys.exit(1)

                # Convert to integer
                try:
                    offset_val = int(val, 16)
                    curr_offset = offset_val
                except ValueError:
                    print(f"ERROR (line {lineno}): Invalid hex value '{val}' for offset")
                    sys.exit(1)
                
                # Check if the current offset within the addr range
                if curr_offset > max_reg_addr:
                    print(f"ERROR: offset {hex(curr_offset)} of the register {curr_reg} exceeds max register address {hex(max_reg_addr)}")
                    sys.exit(1)

                # Store current offset to DB and increment the offset
                reg_db[curr_reg][param] = curr_offset
                curr_offset += OFFSET_PER_REG        
                continue

            # Validate reg description within the register and store to DB
            elif curr_reg is not None and curr_field is None and param == "desc":
                if not val:
                    print(f"ERROR (line {lineno}): Param 'desc' cannot be empty")
                    sys.exit(1)

                # Check for duplicate desc
                if param in reg_db[curr_reg]:
                    print(f"ERROR (line {lineno}): Param 'desc' defined multiple times within the register {curr_reg}")
                    sys.exit(1)

                # Store desc to DB
                reg_db[curr_reg][param] = raw_val           
                continue

            # Verify param ordering
            # 1. Any params defined before reg = INVALID
            # 2. offset must be defined between reg and field, else it is INVALID
            # 3. rstval must be defined after idx for any field
            # 4. Any params other than offset, desc must be defined under field
            if curr_reg is None:
                print(f"ERROR (line {lineno}): Parameter '{param}' defined before any register")
                sys.exit(1)
            if curr_reg is not None and curr_field is not None:
                if param == "offset":
                    print(f"ERROR (line {lineno}): Parameter '{param}' must be defined after 'reg' and before 'field'")
                    sys.exit(1)
                if param == "rstval" and "idx" not in reg_db[curr_reg]["fields"][curr_field]:
                    print(f"ERROR (line {lineno}): Parameter '{param}' must be defined after 'idx' of the field {curr_reg}->{curr_field}")
                    sys.exit(1)
            if curr_reg is not None and curr_field is None:
                print(f"ERROR (line {lineno}): Parameter '{param}' defined before any field")
                sys.exit(1)

            # Check for duplicate params under field
            if curr_reg is not None and curr_field is not None and param in reg_db[curr_reg]["fields"][curr_field]:
                print(f"ERROR (line {lineno}): Parameter '{param}' duplicated for the field {curr_reg}->{curr_field}")
                sys.exit(1)

            # Validate rstval param and store to DB
            if param == "rstval":
                validate_rstval(val, curr_reg, curr_field, lineno)
                continue

            # Validate idx param and store to DB
            if param == "idx":
                validate_idx(val, curr_reg, curr_field, lineno)
                continue

            # Validate swacc param
            if param == "swacc":
                if val not in VALID_SWACC_ARGS:
                    print(f"ERROR (line {lineno}): Invalid swacc argument '{raw_val}'")
                    sys.exit(1)

            # Validate hwacc param
            if param == "hwacc":
                if val not in VALID_HWACC_ARGS:
                    print(f"ERROR (line {lineno}): Invalid hwacc argument '{raw_val}'")
                    sys.exit(1)

            # Validate hwctl param
            if param == "hwctl":
                if val not in VALID_HWCTL_ARGS:
                    print(f"ERROR (line {lineno}): Invalid hwctl argument '{raw_val}'")
                    sys.exit(1)

            # Validate swacc param
            if param == "swevt":
                if val not in VALID_SWEVT_ARGS:
                    print(f"ERROR (line {lineno}): Invalid swevt argument '{raw_val}'")
                    sys.exit(1)

            # Store the validated param to DB (all field params other than rstval, idx would come here)
            if param == "desc":
                if not val:
                    print(f"ERROR (line {lineno}): Param 'desc' cannot be empty")
                    sys.exit(1)
                reg_db[curr_reg]["fields"][curr_field][param] = raw_val
            else:
                reg_db[curr_reg]["fields"][curr_field][param] = val

# Validate register database
def validate_regdb():
    # Global vars
    global reg_db
    global reg_addr_table

    # Verify-
    # 1. Mandatory reg/field params are present
    # 2. Uniqueness of offset 

    # Iterate through each register in the DB and verify reg params and constraints
    for reg_name, reg in reg_db.items():  # Or for reg_name in reg_db, and use reg = reg_db[regname] inside...
        # Verify atleast one field exists per reg
        if not reg["fields"]:
            print(f"ERROR (line {reg['lineno']}): Register {reg_name} must contain at least one field")
            sys.exit(1)

        # Verify offset uniqueness; no two registers can have the same offset
        offset = reg["offset"]
        if offset in reg_addr_table:
            prev_reg = reg_addr_table[offset]
            print(f"ERROR (line {reg['lineno']}): Register {reg_name} uses offset {hex(offset)}, which is already used by {prev_reg}")
            sys.exit(1)
        reg_addr_table[offset] = reg_name

        # Iterate through each field in the register and verify field params: idx, hwacc, swacc
        for field_name, field in reg["fields"].items():
            for param in ["idx", "hwacc", "swacc"]:
                if param not in field:
                    print(f"ERROR (line {field['lineno']}): Field {field_name} in register {reg_name} missing mandatory parameter '{param}'")
                    sys.exit(1)    

    # Validate-
    # 1. The width of each field and verify that there is NO field overlapping in any register
    # 2. hwacc, swacc combination
    # 3. hwctl, swevt in mandatory cases & override in optional cases
    # 4. rstval in mandatory cases & override in optional cases
    # 5. Add default desc if desc not provided

    # Iterate through each register in the DB
    for reg_name, reg in reg_db.items():
        used_bits = 0  # Denotes used bits in a register; if a bit = 1, then it's already used up by some earlier-parsed field in the register
        total_width = 0
        # Iterate through each field in the register
        for field_name, field in reg["fields"].items():
            # Extract params of the field
            idx   = field["idx"]
            width = field["width"]
            swacc = field["swacc"]
            hwacc = field["hwacc"]

            ## Validate field width ##   
            # Total width occupied by fields      
            x, y = [int(v) for v in idx[1:-1].split(":")]
            total_width += width

            # Build bit mask for the current field
            mask = ((1 << width) - 1) << y

            # Overlap check
            if used_bits & mask:
                print(f"ERROR (line {field['lineno']}): Found overlapping fields in register {reg_name} at field {field_name}")
                sys.exit(1)

            # Update used bits in the register
            used_bits |= mask

            ## Validate hwacc, swacc combination ##
            if (swacc, hwacc) not in VALID_HWSWACC_COMBINATIONS:
                print(f"ERROR (line {field['lineno']}): Invalid swacc/hwacc combination: 'swacc={swacc}, hwacc={hwacc}' at field {field_name} in register {reg_name}")
                sys.exit(1)

            ## Validate hwctl in mandatory cases & override with default value in optional cases ##
            if hwacc == "w" or hwacc == "rw":
                if "hwctl" not in field:
                    print(f"ERROR (line {field['lineno']}): Field {field_name} in register {reg_name} missing mandatory parameter 'hwctl'")
                    sys.exit(1)
                elif field["hwctl"] == "na":  # hwctl is mandatory for hardware writeable fields and it cannot be NA
                    print(f"ERROR (line {field['lineno']}): Field {field_name} in register {reg_name} cannot have 'hwctl=na'")
                    sys.exit(1)
            else:
                field["hwctl"] = "na"

            ## Validate swevt in mandatory cases & override with default value in optional cases ##
            if swacc == "w" and hwacc == "na":  # WO fields must have swevt
                if "swevt" not in field:
                    print(f"ERROR (line {field['lineno']}): Field {field_name} in register {reg_name} missing mandatory parameter 'swevt'")
                    sys.exit(1)
                elif field["swevt"] == "na":  # swevt is mandatory for WO fields and it cannot be NA
                    print(f"ERROR (line {field['lineno']}): Field {field_name} in register {reg_name} cannot have 'swevt=na'")
                    sys.exit(1)
            else:
                if "swevt" not in field:
                    field["swevt"] = "na"
                elif (swacc == "na" and hwacc == "na") or (swacc == "w1pul") :  # RSVD, W1PUL fields cannot support swevt
                    field["swevt"] = "na"

            ## Validate rstval in mandatory cases & override with default value in optional cases ##
            #if swacc == "r" and (hwacc == "w" or hwacc == "rw") and field["hwctl"] == "net": # ROW, RO+
                #field["rstval"] = "na"  #CHECKME: May be we can mandate this for documentation purpose; should provide reset value from HW side...
            if swacc == "r" and (hwacc == "na" or hwacc == "r") and ("rstval" in field and field["rstval"] == "na"):  # RO, ROR
                print(f"ERROR (line {field['lineno']}): Field '{field_name}' in register '{reg_name}' should have a valid reset value at 'rstval'")
                sys.exit(1)
            elif swacc == "na" or swacc == "na":  # RSVD
                field["rstval"] = "na"
            elif swacc == "w" and hwacc == "na":  # WO
                field["rstval"] = "na"
            elif swacc == "w1pul": # W1PUL
                field["rstval"] = f"{width}'h0"
            elif "rstval" not in field:  # In all other cases of swacc, hwacc, hwctl it is mandatory to have rstval
                print(f"ERROR (line {field['lineno']}): Field '{field_name}' in register '{reg_name}' missing mandatory parameter 'rstval'")
                sys.exit(1)

            # Add default desc to field, if desc not provided, and store to DB
            if "desc" not in field:
                field["desc"] = DEFAULT_DESC 

        # Total width must not be bigger than the register width!
        if total_width > REG_WIDTH:
            print(f"ERROR (line {reg['lineno']}): Total field width in register '{reg_name}' exceeds {REG_WIDTH}")
            sys.exit(1)

    # Display reg addr space
    DEBUG_MODE and disp_reg_addr_table()

# Add implementation information against each field in the DB
# Implementation can be- flop, constnet (constant net), hwnet (HW driven), na (no driver)
# Add HW controll IO ports associated with each field
# Add bitmap of each register
def add_impl_regdb():
    # Global vars
    global reg_db
    global hw_if_inputs
    global hw_if_outputs

    # Iterate through each register in the DB
    for reg_name, reg in reg_db.items():
        # Iterate through each field in the register
        for field_name, field in reg["fields"].items():
            # Extract params of the field
            swacc = field["swacc"]
            hwacc = field["hwacc"]
            hwctl = field["hwctl"]
            swevt = field["swevt"]

            # Add implementation to the DB
            if swacc == "r" and (hwacc == "na" or hwacc == "r"): # RO, ROR
                field["impl"] = "constnet"
            elif swacc == "r" and (hwacc == "w" or hwacc == "rw") and hwctl == "net": # ROW, RO+
                field["impl"] = "hwnet"
            elif hwacc == "na" and (swacc == "na" or swacc == "w"): # RSVD, WO
                field["impl"] = "na"
            else:
                field["impl"] = "flop"

            # Add HW I/P ports and their widths to the DB
            field["in_ports"] = []
            field["in_ports_w"] = []
            # Only if the field has HW write access, it needs input ports = driven by HW
            if hwacc == "w" or hwacc == "rw":
                hw_if_inputs = True
                if hwctl == "net" or hwctl == "wen":
                    field["in_ports"].append(f"{reg_name}_{field_name}")
                    field["in_ports_w"].append(field["width"])
                if hwctl != "net":
                    field["in_ports"].append(f"{reg_name}_{field_name}_{hwctl}")
                    if hwctl == "set" or hwctl == "clr" or hwctl == "tog" or hwctl == "wen":  # Field wise hwctl, width = 1
                        field["in_ports_w"].append(1)
                    else:  # Bitwise hwctl; setb, clrb, togb, width = field width
                        field["in_ports_w"].append(field["width"])

            # Add HW O/P ports and their widths to the DB
            field["out_ports"] = []
            field["out_ports_w"] = []
            # Only if the field as HW read access or if it's w1pul type, it needs output port to drive HW
            if swacc == "w1pul":
                field["out_ports"].append(f"{reg_name}_{field_name}")  # Bitwise w1pul, width = field width
                field["out_ports_w"].append(field["width"])
                hw_if_outputs = True
            elif hwacc == "r" or hwacc == "rw":
                field["out_ports"].append(f"{reg_name}_{field_name}")
                field["out_ports_w"].append(field["width"])
                hw_if_outputs = True
            # If the field has an associated SW event, it needs output port to drive HW
            if swevt != "na":
                hw_if_outputs = True
                field["out_ports"].append(f"{reg_name}_{field_name}_{swevt}")
                if swevt == "wtrig" or swevt == "rtrig":  # Field wise swevt, width = 1
                    field["out_ports_w"].append(1)
                elif swevt == "w1trig" or swevt == "w0trig":  # Bitwise swevt, width = field width
                    field["out_ports_w"].append(field["width"])


    ## Add bitmap of each register to the DB ##
    # Iterate through each register
    for reg_name, reg in reg_db.items():
        maxidx = REG_WIDTH - 1
        is_reg_resolved = False

        # Start bitmap
        reg["bitmap"] = ""
        reg["bitmap"] += "{"

        # Loop until all the bits in the register are resolved
        while is_reg_resolved == False:
            # Iterate through each field and find the field with the next biggest index
            idx = 0
            field_found = False
            for field_name, field in reg["fields"].items(): 
                fidx = field["idx"]
                fwidth = field["width"]
                fidxmsb = int(fidx[1:-1].split(":")[0])
                if fidxmsb >= idx and fidxmsb <= maxidx:
                    field_found = True
                    curr_fname  = field_name
                    curr_fwidth = fwidth
                    idx = fidxmsb
            if field_found:
                # Find zero padding bits required
                zpw = maxidx - idx
                if zpw > 0:
                    reg["bitmap"] += f"{zpw}'h0, "
                # Calculate next possible biggest index
                maxidx = idx - curr_fwidth
                if maxidx == -1:
                    reg["bitmap"] += f"r_{reg_name}_{curr_fname}"
                    is_reg_resolved = True
                else:
                    reg["bitmap"] += f"r_{reg_name}_{curr_fname}, "
            else:
                # Find zero padding bits required
                zpw = maxidx - idx + 1
                maxidx = -1
                reg["bitmap"] += f"{zpw}'h0"
                is_reg_resolved = True

        # Finish bitmap     
        reg["bitmap"] += "}"

# Hex to Verilog Hex literal
def hex2verhex(val, size):
    digits = size // 4
    return f"{size}'h{val:0{digits}X}"

# Display register database
def disp_regdb():
    # Check if empty
    if not reg_db:
        print("Register database is empty")
        return

    print("\n========= REGISTER DATABASE =========\n")

    for reg_name, reg in reg_db.items():
        print(f"REG  : {reg_name}")
        # Print register parameters
        for param, val in reg.items():
            if param != "fields":
                if param == "offset":
                    val = f"0x{val:0{addr_width_hexdigits}X}"
                print(f"   {param:10} : {val}")
        # Print fields
        print(f"   fields:")
        for field_name, field in reg["fields"].items():
            print(f"      FIELD : {field_name}")
            for fparam, val in field.items():
                print(f"         {fparam:10} : {val}")
        print()

    print("=====================================\n")

# Display register address table
def disp_reg_addr_table():
    # Check if empty
    if not reg_addr_table:
        print("Register address table is empty")
        return

    print("\n========= REGISTER ADDRESS TABLE =========\n")

    print(f"{'OFFSET':10} : REGISTER")
    print(f"{'-'*10}   {'-'*20}")

    for offset in sorted(reg_addr_table):
        reg_name = reg_addr_table[offset]
        print(f"{hex(int(offset)):10} : {reg_name}")

    print("\n==========================================\n")

####  SV FILE GENERATION FUNCTIONS ###
# Print Header
def fprint_header(f, mdlname):
    f.write(f"// Module name   : {mdlname}\n")
    f.write(f"// Description   : Regblock with APB IF\n")
    f.write(f"// Date          : {datetime.now():%Y-%m-%d %H:%M:%S}\n\n")

def fprint_cmnt_header(f, title, width=48, indent=0):
    indent_str = " " * indent
    line = indent_str + "//" + "=" * width + "\n"
    f.write(line)
    f.write(f"{indent_str}// {title}\n")
    f.write(line)

# Format signal/port width
def fmt_width(w, vec=False):
    if not w or w <= 0:
        return ""
    if w == 1:
        return "[0:0]" if vec else ""
    return f"[{w-1}:0]"

# Print IO port
def fprint_port(f, direction, width, name, noprefix=False, comment="", delim=",", indent=3, pad_width=7):
    width_str = fmt_width(width)
    indent_str = " " * indent
    if direction == "output" and not noprefix:
        prefix = "o_"
    elif direction == "input" and not noprefix:
        prefix = "i_"
    else:
        prefix = ""
    line = f"{indent_str}{direction:<6} logic {width_str:>{pad_width}} {prefix}{name}"
    if delim:
        line += delim
    if comment:
        line += "  // " + comment
    f.write(line + "\n")

# Print signal
def fprint_sig(f, dtype, width, name, comment="", delim=";", indent=0, pad_width=7):
    width_str = fmt_width(width)
    indent_str = " " * indent
    line = f"{indent_str}{dtype} {width_str:>{pad_width}} {name}"
    if delim:
        line += delim
    if comment:
        line += "  // " + comment
    f.write(line + "\n")

# Print signal with assignment
def fprint_sig_def(f, dtype, width, name, val, comment="", delim=";", indent=0, pad_width=7, name_pad=1):
    width_str = fmt_width(width)
    indent_str = " " * indent
    line = f"{indent_str}{dtype} {width_str:>{pad_width}} {name:<{name_pad}} = {val}"
    if delim:
        line += delim
    if comment:
        line += "  // " + comment
    f.write(line + "\n")

# Print reset block
def fprint_rstblk(f, signame, rstval, indent=0):
    # Indentation levels
    ind = " " * indent
    ind1 = " " * (indent + 3)
    ind2 = " " * (indent + 6)

    f.write(f"{ind1}if (!resetn) begin\n")
    f.write(f"{ind2}{signame} <= {rstval};\n")
    f.write(f"{ind1}end\n")

# Print HW input/output ports
def fprint_hw_if_ios(f, direction, hw_if_ports):
    if direction == "input":
        ptype   = "in_ports"
        ptype_w = "in_ports_w"
        if hw_if_outputs_cnt > 0:
            last_delim = ","
        else:
            last_delim = ""
    else:
        ptype = "out_ports"
        ptype_w = "out_ports_w"
        last_delim = ""

    # Iterate through register fields and print
    pcount = 0
    for reg_name, reg in reg_db.items():
        is_reg_empty = True
        for field_name, field in reg["fields"].items():
            ports  = field.get(ptype, [])
            widths = field.get(ptype_w, [])
            for i, port in enumerate(ports):
                width = widths[i] if i < len(widths) else None                
                # Insert newline BEFORE starting a new reg
                if is_reg_empty:
                    f.write("\n")
                is_reg_empty = False
                pcount += 1
                # Derive the delimiter to use
                delim = "," if pcount < hw_if_ports else last_delim
                # Print the port
                fprint_port(f, direction, width, port, delim=delim)

# Print module and IOs to SV file
def fprint_module_ios(f, mdlname):
    # Global vars
    global hw_if_inputs_cnt
    global hw_if_outputs_cnt

    # Print Clock, APB IF IOs
    f.write(f"// Module definition\n")
    f.write(f"module {mdlname} (\n")
    fprint_cmnt_header(f, "Clocks & Resets", indent=3)
    fprint_port(f, "input", 1, "clk", noprefix=True)
    fprint_port(f, "input", 1, "resetn", comment="Async active-low", noprefix=True)  # Only active-low reset is supported
    f.write(f"\n")
    fprint_cmnt_header(f, "APB Interface", indent=3)
    fprint_port(f, "input",  addr_width,  "paddr")
    fprint_port(f, "input",  1, "psel")
    fprint_port(f, "input",  1, "penable")
    fprint_port(f, "input",  1, "pwrite")
    fprint_port(f, "input", REG_WIDTH, "pwdata")
    fprint_port(f, "input", STRB_WIDTH, "pstrb")
    fprint_port(f, "output", REG_WIDTH, "prdata")
    if hw_if_inputs or hw_if_outputs:
        fprint_port(f, "output", 1, "pready")
        f.write("\n")
        fprint_cmnt_header(f, "HW Interface", indent=3)
        for reg in reg_db.values():
            for field in reg["fields"].values():
                hw_if_inputs_cnt  += len(field.get("in_ports", []))
                hw_if_outputs_cnt += len(field.get("out_ports", []))
    else:
        print_port(f, "output", 1, "o_pready", delim="")

    # Print HW inputs
    if hw_if_inputs:
        f.write("\n   // HW Inputs  //\n")
        fprint_hw_if_ios(f, "input", hw_if_inputs_cnt)

    # Print HW outputs
    if hw_if_outputs:
        f.write("\n   // HW Outputs //\n")
        fprint_hw_if_ios(f, "output", hw_if_outputs_cnt)

    # END
    f.write(f");\n")

# Print assign statements to HW IF outputs
def fprint_assign_hw_if_outs(f):
    if hw_if_outputs:
        f.write("\n")
        fprint_cmnt_header(f, "HW Outputs")
        for reg_name, reg in reg_db.items():
            is_reg_empty = True

            # Find max port name length for alignment
            reg_ports = []
            for field in reg["fields"].values():
                reg_ports.extend(field.get("out_ports", []))
            max_len = max((len(port) for port in reg_ports), default=0)

            # Print each port
            for field_name, field in reg["fields"].items():
                ports  = field.get("out_ports", [])
                for i, port in enumerate(ports):
                    f.write(f"assign o_{port:<{max_len}} = {port};\n")
                    is_reg_empty = False
            if is_reg_empty == False:
                f.write("\n")

# Print address map
def fprint_addr_map(f):
    f.write("\n")
    fprint_cmnt_header(f, "Register Address Map")   

    # Find max reg name length for alignment
    max_len = 0
    for reg_name, reg in reg_db.items():
        name = f"{reg_name.upper()}_ADDR"
        if len(name) > max_len:
            max_len = len(name)
    # Print each register
    for reg_name, reg in reg_db.items():
        name = f"{reg_name.upper()}_ADDR"
        addr = reg['offset']
        f.write(f"localparam {name:<{max_len}} = {addr_width}'h{addr:X};\n")

# Print APB decoded signals
def fprint_apb_decd_sig(f):
    f.write("\n")
    fprint_cmnt_header(f, "APB decoded signals")
    fprint_sig(f, "logic", addr_width, "paddr")
    fprint_sig(f, "logic", REG_WIDTH, "prdata")
    fprint_sig(f, "logic", 1, "req_rd, req_wr, sw_wren, sw_rden")
    f.write("\n")
    f.write(f"localparam ADDR_LSB = $clog2({REG_WIDTH}/8);\n")
    f.write(f"assign paddr = {{i_paddr[{addr_width-1}:ADDR_LSB], {{ADDR_LSB{{1'b0}}}}}};\n")

# Print APB IF Control FSM
def fprint_apb_ctrl_fsm(f, indent=0):
    # Indentation levels
    ind = " " * indent
    ind1 = " " * (indent + 3)
    ind2 = " " * (indent + 6)

    f.write("\n")
    fprint_cmnt_header(f, "APB IF Control FSM")

    f.write(f"{ind}// FSM states\n")
    f.write(f"{ind}typedef enum logic [1:0]\n")
    f.write(f"{ind}{{\n")
    f.write(f"{ind1}IDLE     = 2'b00,\n")
    f.write(f"{ind1}W_ACCESS = 2'b01,\n")
    f.write(f"{ind1}R_ACCESS = 2'b10,\n")
    f.write(f"{ind1}R_FINISH = 2'b11\n")
    f.write(f"{ind}}}  state_t;\n")

    f.write(f"{ind}// State register\n")
    f.write(f"{ind}state_t state_ff;\n\n")

    f.write(f"{ind}// Read/write requests\n")
    f.write(f"{ind}assign req_rd  = i_psel && ~i_pwrite;\n")
    f.write(f"{ind}assign req_wr  = i_psel &&  i_pwrite;\n")
    f.write(f"{ind}assign sw_wren = (state_ff == W_ACCESS) && req_wr && i_penable;\n")
    f.write(f"{ind}assign sw_rden = (state_ff == R_ACCESS) && req_rd && i_penable;\n\n")

    f.write(f"{ind}// FSM\n")
    f.write(f"{ind}{always_ff_begin}\n")

    f.write(f"{ind1}// Reset\n")
    f.write(f"{ind1}if (!resetn) begin\n")
    f.write(f"{ind2}state_ff <= IDLE;\n")
    f.write(f"{ind2}o_prdata <= {REG_WIDTH}'h0;\n")
    f.write(f"{ind2}o_pready <= 1'b0;\n")
    f.write(f"{ind1}end\n")

    f.write(f"{ind1}// Out of reset\n")
    f.write(f"{ind1}else begin\n")
    f.write(f"{ind2}// APB control FSM\n")
    f.write(f"{ind2}case (state_ff)\n\n")

    # IDLE
    f.write(f"{ind2}   // Idle State : waits for psel signal and decodes access type\n")
    f.write(f"{ind2}   IDLE : begin\n")
    f.write(f"{ind2}      if (req_wr) begin\n")
    f.write(f"{ind2}         o_pready <= 1'b1;      // Write access has no wait states\n")
    f.write(f"{ind2}         state_ff <= W_ACCESS;\n")
    f.write(f"{ind2}      end       \n")
    f.write(f"{ind2}      else if (req_rd) begin\n")
    f.write(f"{ind2}         o_pready <= 1'b0;      // Read access has wait states\n")
    f.write(f"{ind2}         state_ff <= R_ACCESS;\n")
    f.write(f"{ind2}      end           \n")
    f.write(f"{ind2}   end\n\n")

    # W_ACCESS
    f.write(f"{ind2}   // Write Access State : writes addressed-register\n")
    f.write(f"{ind2}   W_ACCESS : begin\n")
    f.write(f"{ind2}       o_pready <= 1'b0;\n")
    f.write(f"{ind2}       state_ff <= IDLE;\n")
    f.write(f"{ind2}   end\n\n")

    # R_ACCESS
    f.write(f"{ind2}   // Read Access State : reads addressed-register\n")
    f.write(f"{ind2}   R_ACCESS : begin\n")
    f.write(f"{ind2}      o_prdata <= prdata;\n")
    f.write(f"{ind2}      o_pready <= 1'b1;\n")
    f.write(f"{ind2}      state_ff <= R_FINISH;\n")
    f.write(f"{ind2}   end\n\n")

    # R_FINISH
    f.write(f"{ind2}   // Read Finish state : All read accesses finish here\n")
    f.write(f"{ind2}   R_FINISH : begin\n")
    f.write(f"{ind2}      o_pready <= 1'b0;\n")
    f.write(f"{ind2}      state_ff <= IDLE;\n")
    f.write(f"{ind2}   end\n\n")

    # Default
    f.write(f"{ind2}   // Default state\n")
    f.write(f"{ind2}   default : ;\n\n")

    f.write(f"{ind2}endcase\n")
    f.write(f"{ind1}end\n")
    f.write(f"{ind}end\n")

# Print Reg access decode logic
def fprint_regacc_decd(f):
    f.write("\n")
    fprint_cmnt_header(f, "Register access decode logic")
    for reg_name, reg in reg_db.items():
        base = reg_name.lower()
        addr = f"{reg_name.upper()}_ADDR"
        f.write(f"wire {base}_hit = (paddr == {addr});\n")
        f.write(f"wire {base}_wr  = {base}_hit && sw_wren;\n")
        f.write(f"wire {base}_rd  = {base}_hit && sw_rden;\n\n")

# Print Reg fields declaration
def fprint_reg_fields(f):
    f.write("\n")
    fprint_cmnt_header(f, "Register fields")

    # Iterate through each register in the DB
    for reg_name, reg in reg_db.items():
        is_reg_empty = True
        # Iterate through each field in the register
        for field_name, field in reg["fields"].items():
            # Extract params of the field
            fwidth = field["width"]
            impl   = field["impl"]
            swevt  = field["swevt"]
            fname  = reg_name + "_" + field_name
            # Declare the field if it has a HW implementation
            if impl != "na":
                is_reg_empty = False
                fprint_sig(f, "logic", fwidth, fname)
            # Declare the SWEVT signal, if any...
            if swevt != "na":
                is_reg_empty = False
                if swevt == "wtrig" or swevt == "rtrig":  # Field wise swevt, width = 1
                    fprint_sig(f, "logic", 1, fname + "_" + swevt)
                elif swevt == "w1trig" or swevt == "w0trig":  # Bitwise swevt, width = fwidth
                    fprint_sig(f, "logic", fwidth, fname + "_" + swevt)
        if is_reg_empty == False:
                f.write("\n")        

# Print Reg field read value assignment
def fprint_reg_fields_readval_assign(f):
    f.write("\n")
    fprint_cmnt_header(f, "Register fields read values")


    # Iterate through each register in the DB
    for reg_name, reg in reg_db.items():
        is_reg_empty = True

        # Find max field name length for alignment
        reg_fields = [f"r_{reg_name}_{f}" for f in reg["fields"]]
        max_len = max((len(name) for name in reg_fields), default=0)

        # Iterate through each field in the register
        for field_name, field in reg["fields"].items():
            # Extract params of the field
            fwidth = field["width"]
            impl   = field["impl"]
            swacc  = field["swacc"]
            fname  = reg_name + "_" + field_name
            # Assign the read value = 0 if RSVD or WO* access type, else read value = field value
            if impl == "na" or swacc == "w":
                is_reg_empty = False
                fprint_sig_def(f, "wire", fwidth, "r" + "_" + fname, str(fwidth) + "'h0", name_pad=max_len)
            else:
                is_reg_empty = False
                fprint_sig_def(f, "wire", fwidth, "r" + "_" + fname, fname, name_pad=max_len)
        if is_reg_empty == False:
                f.write("\n")

# Print Reg field write logic and SWEVT generation
# Assumptions 
# -- SW writes precedes over HW writes
# -- W1PUL should be one-cycle pulse always, as SW write cannot happen in consecutive cycles        
def fprint_reg_fields_wrlogic(f, indent=0):
    # Indentation levels
    ind = " " * indent
    ind1 = " " * (indent + 3)
    ind2 = " " * (indent + 6)

    f.write("\n")
    fprint_cmnt_header(f, "Register fields write logic & SWEVT generation")

    # Iterate through each register in the DB
    for reg_name, reg in reg_db.items():
        is_reg_empty = True
        # Iterate through each field in the register
        for field_name, field in reg["fields"].items():
            # Flags
            is_rstval = False
            is_swacc  = False
            is_hwacc  = False
            # Extract params of the field
            fwidth = field["width"]
            idx    = field["idx"]
            msb, lsb = map(int, idx.strip("[]").split(":"))
            impl   = field["impl"]
            swevt  = field["swevt"]
            swacc  = field["swacc"]
            hwacc  = field["hwacc"]
            hwctl  = field["hwctl"]
            rstval = field["rstval"]
            fname  = reg_name + "_" + field_name

            # RO, ROR, impl = constnet
            if impl == "constnet":
                f.write(f"{ind}// {reg_name}->{field_name}\n")
                f.write(f"{ind}assign {fname} = {rstval};\n\n")

            # ROW, RO+, impl = hwnet
            elif impl == "hwnet":
                f.write(f"{ind}// {reg_name}->{field_name}\n")
                f.write(f"{ind}assign {fname} = i_{fname};\n\n")

            # RW, RWR, RWW, RW+, ROW, RO+, WOR, WO+, W1CLR/SET/PUL/TOG, RCLR, RSET, impl = flop
            elif impl == "flop":
                # always_ff block begin
                f.write(f"{ind}// {reg_name}->{field_name}\n")
                f.write(f"{ind}{always_ff_begin}\n")

                ## Reset block ##
                if rstval != "na":
                    is_rstval = True
                    f.write(f"{ind1}// Reset\n")
                    fprint_rstblk(f, fname, rstval)

                ## SW write ##
                # RW, RWR, RWW, RW+, WOR, WO+, W1CLR/SET/PUL/TOG, RCLR, RSET
                if swacc == "rw" or swacc == "w" or swacc == "w1clr" or swacc == "w1set" or swacc == "w1pul" or swacc == "w1tog" or swacc == "rclr" or swacc == "rset":
                    is_swacc = True
                    # Begin                   
                    if is_rstval:
                        if swacc == "rclr" or swacc == "rset":
                            if swacc == "rclr":
                                f.write(f"{ind1}// SW Clear on Read\n")
                            else:
                                f.write(f"{ind1}// SW Set on Read\n")
                            f.write(f"{ind1}else if ({reg_name}_rd) begin\n")
                        else:
                            f.write(f"{ind1}// SW Write\n") 
                            f.write(f"{ind1}else if ({reg_name}_wr) begin\n")
                    else:
                        if swacc == "rclr" or swacc == "rset":
                            f.write(f"{ind1}// SW Modify on Read\n") 
                            f.write(f"{ind1}if ({reg_name}_rd) begin\n")
                        else:
                            f.write(f"{ind1}// SW Write\n") 
                            f.write(f"{ind1}if ({reg_name}_wr) begin\n")

                    # RCLR
                    if swacc == "rclr":
                        f.write(f"{ind2}{fname} <= '0;\n")
                    # RSET
                    elif swacc == "rset":
                        f.write(f"{ind2}{fname} <= '1;\n")
                    # RW, RWR, RWW, RW+, WOR, WO+, W1CLR/SET/PUL/TOG
                    elif swacc == "rw" or swacc == "w" or swacc == "w1clr" or swacc == "w1set" or swacc == "w1pul" or swacc == "w1tog":   
                        # PSTRB mapping
                        pstrb_start = lsb // 8
                        pstrb_end   = msb // 8
                        for i in range(pstrb_start, pstrb_end + 1):
                            byte_lsb = i * 8
                            byte_msb = i * 8 + 7
                            slice_lsb = max(lsb, byte_lsb)
                            slice_msb = min(msb, byte_msb)

                            # Convert to field-local indexing
                            fld_lsb = slice_lsb - lsb
                            fld_msb = slice_msb - lsb

                            f.write(f"{ind2}if (i_pstrb[{i}]) ")
                            if swacc == "rw" or swacc == "w":  # RW, RWR, RWW, RW+, WOR, WO+
                                f.write(f"{fname}[{fld_msb}:{fld_lsb}] <= i_pwdata[{slice_msb}:{slice_lsb}];\n")
                            elif swacc == "w1set":  # W1SET
                                f.write(f"{fname}[{fld_msb}:{fld_lsb}] <= {fname}[{fld_msb}:{fld_lsb}] | i_pwdata[{slice_msb}:{slice_lsb}];\n")
                            elif swacc == "w1clr":  # W1CLR
                                f.write(f"{fname}[{fld_msb}:{fld_lsb}] <= {fname}[{fld_msb}:{fld_lsb}] & ~i_pwdata[{slice_msb}:{slice_lsb}];\n")
                            elif swacc == "w1tog":  # W1TOG
                                f.write(f"{fname}[{fld_msb}:{fld_lsb}] <= {fname}[{fld_msb}:{fld_lsb}] ^ i_pwdata[{slice_msb}:{slice_lsb}];\n")
                            elif swacc == "w1pul":  # W1PUL
                                f.write(f"{fname}[{fld_msb}:{fld_lsb}] <= i_pwdata[{slice_msb}:{slice_lsb}];\n")

                    # End
                    f.write(f"{ind1}end\n")
                    if swacc == "w1pul":  # W1PUL
                        f.write(f"{ind1}// Clear the pulse\n") 
                        f.write(f"{ind1}else begin\n")
                        f.write(f"{ind2}{fname} <= '0;\n")
                        f.write(f"{ind1}end\n")

                ## HW write ##
                # RWW, RW+, ROW, RO+, WO+, W1CLR/SET/TOG, RCLR, RSET
                if hwacc == "w" or hwacc == "rw":
                    is_hwacc = True
                    # Begin
                    f.write(f"{ind1}// HW Write\n")
                    if is_rstval or is_swacc:
                        f.write(f"{ind1}else begin\n")
                    # Write
                    if hwctl == "set":
                        f.write(f"{ind2}{fname} <= i_{fname}_{hwctl} ? '1 : {fname};\n")
                    elif hwctl == "clr":
                        f.write(f"{ind2}{fname} <= i_{fname}_{hwctl} ? '0 : {fname};\n")
                    elif hwctl == "tog":
                        f.write(f"{ind2}{fname} <= i_{fname}_{hwctl} ? ~{fname} : {fname};\n")
                    elif hwctl == "wen":
                        f.write(f"{ind2}{fname} <= i_{fname}_{hwctl} ? i_{fname} : {fname};\n")
                    elif hwctl == "net":
                        f.write(f"{ind2}{fname} <= i_{fname};\n")
                    elif hwctl == "setb":
                        f.write(f"{ind2}{fname} <= {fname} | i_{fname}_{hwctl};\n")
                    elif hwctl == "clrb":
                        f.write(f"{ind2}{fname} <= {fname} & ~i_{fname}_{hwctl};\n")
                    elif hwctl == "togb":
                        f.write(f"{ind2}{fname} <= {fname} ^ i_{fname}_{hwctl};\n")
                    # End
                    if is_rstval or is_swacc:
                        f.write(f"{ind1}end\n")   

                # always_ff block end
                f.write(f"{ind}end\n\n")

            # WO, impl = na, but has SWEVT
            #elif impl == "na" and swevt != "na":

            ## SWEVT ##
            if swevt != "na":
                # always_ff block begin
                f.write(f"{ind}// SWEVT: {reg_name}->{field_name}_{swevt}\n")
                f.write(f"{ind}{always_ff_begin}\n")

                # Reset block
                f.write(f"{ind1}// Reset\n")
                if swevt == "wtrig" or swevt == "rtrig":
                    swevt_rstval = "1'h0"
                elif swevt == "w1trig" or swevt == "w0trig":
                    swevt_rstval = str(fwidth) + "'h0"
                fprint_rstblk(f, fname + "_" + swevt, swevt_rstval)

                # PSTRB mapping
                pstrb_start = lsb // 8
                pstrb_end   = msb // 8

                # WTRIG
                if swevt == "wtrig":
                    f.write(f"{ind1}// SW Write event pulse\n") 
                    f.write(f"{ind1}else if ({reg_name}_wr) begin\n")
                    f.write(f"{ind2}if (|i_pstrb[{pstrb_end}:{pstrb_start}]) ")
                    f.write(f"{fname}_{swevt} <= 1'h1;\n")
                    f.write(f"{ind1}end\n")
                    f.write(f"{ind1}// Clear the SWEVT pulse\n") 
                    f.write(f"{ind1}else begin\n")
                    f.write(f"{ind2}{fname}_{swevt} <= 1'h0;\n")
                    f.write(f"{ind1}end\n")
                # RTRIG
                elif swevt == "rtrig":
                    f.write(f"{ind1}// SW Read event pulse\n") 
                    f.write(f"{ind1}else if ({reg_name}_rd) begin\n")
                    f.write(f"{ind2}{fname}_{swevt} <= 1'h1;\n")
                    f.write(f"{ind1}end\n")
                    f.write(f"{ind1}// Clear the SWEVT pulse\n") 
                    f.write(f"{ind1}else begin\n")
                    f.write(f"{ind2}{fname}_{swevt} <= 1'h0;\n")
                    f.write(f"{ind1}end\n")
                # W1TRIG
                elif swevt == "w1trig":
                    f.write(f"{ind1}// SW Write 1 event pulse\n") 
                    f.write(f"{ind1}else if ({reg_name}_wr) begin\n")
                # W0TRIG
                elif swevt == "w0trig":
                    f.write(f"{ind1}// SW Write 0 event pulse\n") 
                    f.write(f"{ind1}else if ({reg_name}_wr) begin\n")

                # W1/W0TRIG
                if swevt == "w1trig" or swevt == "w0trig":
                    for i in range(pstrb_start, pstrb_end + 1):
                        byte_lsb = i * 8
                        byte_msb = i * 8 + 7
                        slice_lsb = max(lsb, byte_lsb)
                        slice_msb = min(msb, byte_msb)

                        # Convert to field-local indexing
                        fld_lsb = slice_lsb - lsb
                        fld_msb = slice_msb - lsb

                        f.write(f"{ind2}if (i_pstrb[{i}]) ")
                        if swevt == "w1trig":
                            f.write(f"{fname}_{swevt}[{fld_msb}:{fld_lsb}] <= i_pwdata[{slice_msb}:{slice_lsb}];\n")
                        else:
                            f.write(f"{fname}_{swevt}[{fld_msb}:{fld_lsb}] <= ~i_pwdata[{slice_msb}:{slice_lsb}];\n")
                    f.write(f"{ind1}end\n")
                    f.write(f"{ind1}// Clear the SWEVT pulse\n") 
                    f.write(f"{ind1}else begin\n")
                    f.write(f"{ind2}{fname}_{swevt} <= '0;\n")
                    f.write(f"{ind1}end\n")

                # always_ff block end
                f.write(f"{ind}end\n\n")


# Print Read data Mux
def fprint_rdata_mux(f, indent=0):
    # Indentation levels
    ind  = " " * indent
    ind1 = " " * (indent + 3)
    ind2 = " " * (indent + 6)

    f.write("\n")
    fprint_cmnt_header(f, "Read Data Mux")

    f.write(f"{ind}always_comb begin\n")
    f.write(f"{ind1}if (!sw_rden) begin\n")
    f.write(f"{ind2}prdata = 32'h0; \n")
    f.write(f"{ind1}end\n")
    f.write(f"{ind1}else begin\n")
    f.write(f"{ind2}case (paddr)\n")

    # Find max reg name length for alignment
    max_len = 0
    for reg_name, reg in reg_db.items():
        name = f"{reg_name.upper()}_ADDR"
        if len(name) > max_len:
            max_len = len(name)
    # Assign prdata to each register
    for reg_name, reg in reg_db.items():
        addr = f"{reg_name.upper()}_ADDR"
        bitmap = reg["bitmap"]
        f.write(f"{ind2}   {addr:<{max_len}} : prdata = {bitmap};\n")

    # Default
    f.write(f"{ind2}   {'default':<{max_len}} : prdata = 32'h0;\n")

    f.write(f"{ind2}endcase\n")
    f.write(f"{ind1}end\n")
    f.write(f"{ind}end\n")


#### CONSTANTS ####
MIN_ADDR_WIDTH = 2
MAX_ADDR_WIDTH = 16
REG_WIDTH = 32
REG_SIZE_IN_BYTES = int(REG_WIDTH/8)
OFFSET_PER_REG = 4
ADDR_LSIDX = 2  # Least valid index in byte-addressing scheme
STRB_WIDTH = REG_SIZE_IN_BYTES

ASYNC_LOW_RST = 0
SYNC_LOW_RST = 1

# Valid params & arguments under register definitions
# Valid reg params
VALID_REG_PARAMS = [
    "reg",
    "offset",
    "idx",
    "field",
    "swacc",
    "hwacc",
    "hwctl",
    "swevt",
    "rstval",
    "desc"
]
# Valid swacc args
VALID_SWACC_ARGS = [
    "w",
    "r",
    "rw",
    "na",
    "w1clr",
    "w1set",
    "w1pul",
    "w1tog",
    "rclr",
    "rset"
]
# Valid hwacc args
VALID_HWACC_ARGS = [
    "w",
    "r",
    "rw",
    "na"
]
# Valid hwctl args
VALID_HWCTL_ARGS = [
    "set",
    "clr",
    "tog",
    "wen",
    "net",
    "setb",
    "clrb",
    "togb",
    "na"
]
# Valid swevt args
VALID_SWEVT_ARGS = [
    "wtrig",
    "w1trig",
    "w0trig",
    "rtrig",
    "na"
]
# Valid hwacc, swacc combinations
VALID_HWSWACC_COMBINATIONS = [
    ("rw", "na"),
    ("rw", "r"),
    ("rw", "w"),
    ("rw", "rw"),

    ("r", "na"),
    ("r", "r"),
    ("r", "w"),
    ("r", "rw"),

    ("w", "na"),
    ("w", "r"),
    ("w", "rw"),

    ("na", "na"),

    ("w1clr", "w"),
    ("w1clr", "rw"),

    ("w1set", "w"),
    ("w1set", "rw"),

    ("w1pul", "r"),

    ("w1tog", "w"),
    ("w1tog", "rw"),

    ("rclr", "w"),
    ("rclr", "rw"),

    ("rset", "w"),
    ("rset", "rw")
]

############################ Configurable ##################################
DEBUG_MODE   = 1                # 1 - Enable debug messages
DEFAULT_DESC = ""               # Default reg/field descriptions
RST_TYPE     = ASYNC_LOW_RST    # APB reset; ASYNC_LOW_RST or SYNC_LOW_RST
SUFFIX_OFILE = "_apb_top"    # SV file suffix
EN_BRANDING  = 1  # 0 - to disable RegForge branding in generated SV files
############################################################################

#### Global PARAMs ####
base_addr = 0x0
end_addr = None
max_reg_addr = None
max_regs = None
addr_width = None
addr_width_hexdigits = None
reg_cnt = 0
reg_db = {}
reg_addr_table = {}
mdlname = None
hw_if_inputs = False
hw_if_outputs = False
hw_if_inputs_cnt = 0
hw_if_outputs_cnt = 0
always_ff_begin = None

#### MAIN ####
def main():
    # Global vars
    global always_ff_begin

    # Derive always_ff block begin
    if RST_TYPE == ASYNC_LOW_RST:
        always_ff_begin = "always_ff @(posedge clk or negedge resetn) begin"  # Async reset
    else:
        always_ff_begin = "always_ff @(posedge clk) begin"  # Sync reset

    # Check argument count
    if len(sys.argv) != 2:
        print("ERROR: Invalid arguments.\n")
        usage()
        sys.exit(1)

    # Check regfile existence
    infile = sys.argv[1]
    if not os.path.isfile(infile):
        print(f"ERROR: File '{infile}' not found.\n")
        usage()
        sys.exit(1)

    # Welcome messages
    print('    ____             ______                    ')
    print('   / __ \\___  ____ _/ ____/___  _________ ____ ')
    print('  / /_/ / _ \\/ __ `/ /_  / __ \\/ ___/ __ `/ _ \\')
    print(' / _, _/  __/ /_/ / __/ / /_/ / /  / /_/ /  __/')
    print('/_/ |_|\\___/\\__, /_/    \\____/_/   \\__, /\\___/ ')
    print('           /____/                 /____/       ')    
    print(f"Input file : {infile}")

    # Verify the regfile structure
    print("\nVerifying the regfile structure...\n")
    verify_regfile_struct(infile)
    print(f"ADDRESS SPACE")
    print(f"-------------")
    print(f"Address width                  = {addr_width}")
    print(f"Start address                  = {base_addr:#x}")
    print(f"End address                    = {end_addr:#x}")
    print(f"Max reg addr                   = {max_reg_addr:#x}")
    print(f"Register width                 = {REG_WIDTH}-bit")
    print(f"Max no. of registers supported = {max_regs}")
    print(f"No. of registers in regfile    = {reg_cnt}")

    print("\nStarting RegForge...\n")

    # Create register database
    print(f"**Creating register database**")
    create_regdb(infile)
    print(f"Register database created successfully!")

    # Validate register database
    print(f"**Validating register database**")
    validate_regdb()
    add_impl_regdb()
    DEBUG_MODE and disp_regdb()

    # Create SV file and print default content to it
    outfile = f"{mdlname}{SUFFIX_OFILE}.sv"
    try:
        with open(outfile, "w") as f:
            # Branding
            if EN_BRANDING:
                f.write(f"// Generated by RegForge //\n")
                f.write(f"// Try RegForge here - https://github.com/iammituraj/RegForge\n\n")

            # Module begin, ports
            fprint_header(f, mdlname)
            fprint_module_ios(f, mdlname)

            # Address map
            fprint_addr_map(f)

            # APB decoded signals
            fprint_apb_decd_sig(f)

            # APB IF Control FSM
            fprint_apb_ctrl_fsm(f)

            # Reg access decode logic
            fprint_regacc_decd(f)

            # Reg fields declarations
            fprint_reg_fields(f)

            # Reg fields write logic, SWEVT generation
            fprint_reg_fields_wrlogic(f)

            # Reg fields read value assignment
            fprint_reg_fields_readval_assign(f)

            # Read data mux
            fprint_rdata_mux(f)

            # HW outputs
            fprint_assign_hw_if_outs(f)

            # End module
            f.write(f"\nendmodule")
    except Exception as e:
        print(f"ERROR: Could not create file: {outfile} successfully :(")
        print(e)

if __name__ == "__main__":
    main()