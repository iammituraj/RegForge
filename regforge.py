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
# Last modified on : Mar-2026
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
    
    # Local vars
    start_addrspace_cnt = 0
    start_regs_cnt = 0
    is_addrspace_present = False
    is_regs_present = False
    is_atleast_one_reg_present = False
    is_addr_width_present = False

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
            
            # Verify if atleast one register is present
            if is_addrspace_present and is_regs_present:
                if "=" in line:
                    param, val = [x.strip() for x in line.split("=", 1)]
                    if param == "reg" and val:
                        is_atleast_one_reg_present = True
                        reg_cnt += 1
    
    # Verify the regfile skeltal structure
    # 1. Labels START_ADDRSPACE, START_REGS defined?
    # 2. addr_width param defined?
    # 3. Atleast one register defined?
    # 4. Register count must be within the address space boundaries
    if start_addrspace_cnt != 1:
        print("ERROR: File must contain exactly one #START_ADDRSPACE label")
        sys.exit(1)
    if start_regs_cnt != 1:
        print("ERROR: File must contain exactly one #START_REGS label")
        sys.exit(1)
    if not is_addr_width_present:
        print("ERROR: File missing the parameter addr_width")
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
# │   │
# │   └── fields                          # Dictionary of fields in the register
# │       ├── <field_name>                # Example: "tx_ready"
# │       │   ├── idx    : int            # Starting bit index of field
# │       │   ├── width  : int            # Field width in bits
# │       │   ├── swacc  : str            # Software access type
# │       │   ├── hwacc  : str            # Hardware access type
# │       │   ├── rstval : str            # Reset value (example: "1'h0")
# │       │   ├── desc   : str            # Field description
# │       │   └── lineno : int            # Line number of field in regfile
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
            if swacc == "r" and (hwacc == "w" or hwacc == "rw") and hwctl == "net": # ROW, RO+
                field["rstval"] = "na"
            elif swacc == "r" and (hwacc == "na" or hwacc == "r") and ("rstval" in field and field["rstval"] == "na"):
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
# Add IO ports associated with each field
def add_impl_regdb():
    # Global vars
    global reg_db

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

            # Add I/P ports to the DB
            field["in_ports"] = []
            # Only if the field has HW write access, it needs input ports = driven by HW
            if hwacc == "w" or hwacc == "rw":
                if hwctl == "net" or hwctl == "wen":
                    field["in_ports"].append(f"{reg_name}_{field_name}")
                if hwctl != "net":
                    field["in_ports"].append(f"{reg_name}_{field_name}_{hwctl}")

            # Add O/P ports to the DB
            field["out_ports"] = []
            # Only if the field as HW read access, it needs output port to drive HW
            if swacc == "w1pul":
                field["out_ports"].append(f"{reg_name}_{field_name}_w1pul")
            elif hwacc == "r" or hwacc == "rw":
                field["out_ports"].append(f"{reg_name}_{field_name}")
            # If the field has an associated SW event, it needs output port to drive HW
            if swevt != "na":
                field["out_ports"].append(f"{reg_name}_{field_name}_{swevt}")

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

#### Configurable ####
DEBUG_MODE   = 1                # 1 - Enable debug messages
DEFAULT_DESC = ""               # Default reg/field descriptions
RST_TYPE     = ASYNC_LOW_RST    # APB reset
SUFFIX_OFILE = "_apb_top.sv"    # SV file suffix

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

#### MAIN ####
def main():

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

    # Generate outfile name
    base = os.path.splitext(infile)[0]
    outfile = base + SUFFIX_OFILE
    
    # Welcome messages
    print('    ____             ______                    ')
    print('   / __ \\___  ____ _/ ____/___  _________ ____ ')
    print('  / /_/ / _ \\/ __ `/ /_  / __ \\/ ___/ __ `/ _ \\')
    print(' / _, _/  __/ /_/ / __/ / /_/ / /  / /_/ /  __/')
    print('/_/ |_|\\___/\\__, /_/    \\____/_/   \\__, /\\___/ ')
    print('           /____/                 /____/       ')    
    print(f"Input file : {infile}")
    print(f"Output file: {outfile}")

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

if __name__ == "__main__":
    main()