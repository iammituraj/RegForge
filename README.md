# RegForge

RegForge is a tool that generates APB register blocks for your RTL designs.

**Input**
= Registers with access rules described in a plain text file.

**Output**
= APB register block in synthesisable RTL (System Verilog).

---

## Features

- Ability to configure each register field with SW and HW access policies.
- Supports automatic/manual address allocation of each register.
- Generates Regblock with 32-bit APB IF to access the full register address space.
	- 32-bit APB IF
	- Write access = 2 cycles, Read access = 3 cycles
	- Configurable address width
	- Configurable reset- Asynchronous or Synchronous active-low

---

## Requirements

- Python 3.9 or later
- Linux/macOS/WSL recommended

---

## Usage


```bash
regforge.py <regfile>
```

Example:

```bash
regforge.py uart_regs.txt
```

Output:

```text
uart_regblock.sv
```

---

## Configuring the script
There are some configurable parameters in the script with default value as given below.

| Parameter      | Default          | Description |
|----------------|------------------|-------------|
| `DEBUG_MODE`     | 1              | Enable debug messages. Set to `0` to disable. |
| `DEFAULT_DESC`   |             | Default description used when a register or field description is not provided. |
| `RST_TYPE`       | `ASYNC_LOW_RST`  | Reset type for generated APB register block. Valid values: `ASYNC_LOW_RST`, `SYNC_LOW_RST`. |
| `SUFFIX_OFILE`   | `"_apb_top"`     | Suffix appended to the generated System Verilog filename. |
| `EN_BRANDING`    | `1`              | Include `RegForge` branding banner in generated RTL. Set to `0` to disable. |

---

## Register File Structure

A register file contains two mandatory sections:

```text
#START_ADDRSPACE
...
#START_REGS
...

// Single line comments are supported anywhere in the register file like this :)
```

### Address Space Section

Example:

```text
#START_ADDRSPACE

mdlname = uart_regblock
addr_width = 8
```

| Parameter  | Required | Description |
|------------|----------|-------------|
| `mdlname`    | Yes      | Generated RTL module name |
| `addr_width` | Yes      | APB address width in bits |

- Supported `addr_width` range = `[2, 32]`

---

## Register Definition

Register can be defined like below. **Atleast one register** must be there in the address space.
Each register must be having unique name.

Example:

```text
reg    = control
offset = 0x08
desc   = Control register
```

---

### Register Parameters

| Parameter | Required | Description |
|------------|------------|------------|
| `reg` | Yes | Register name |
| `offset` | No | Register offset |
| `desc` | No | Register description |

- The `offset` must be in Hexa format. And must be within the max address of the address space. The offset addresses are unique for each register.
- If `offset` is omitted, RegForge automatically assigns the next available address = previous address + 0x4.
- If `desc` is omitted, RegForge automatically assigns the default description = `DEFAULT_DESC`

---

## Field Definition

Fields of the register can be defined like below. **Atleast one field** must be there in a register. Each field must be having unique name.

Example:

```text
field  = txen
idx    = [0:0]
swacc  = rw
hwacc  = r
rstval = 0x1
desc   = Enable transmitter
```

---

### Field Parameters

| Parameter | Required | Description |
|------------|------------|------------|
| `field` | Yes | Field name |
| `idx` | Yes | Index `[msb:lsb]` |
| `swacc` | Yes | Software access policy |
| `hwacc` | Yes | Hardware access policy |
| `rstval` | Depends | Reset value |
| `hwctl` | Yes, iff HW writeable fields | HW control type
| `swevt` | Yes, iff `WO` field | SW event type
| `desc` | No | Description |

- Every other field param must be defined after defining the params - `field`, `idx`.
- If `desc` is omitted, RegForge automatically assigns the default description = `DEFAULT_DESC`
- It's **not mandatory** to map all bits in the register to fields.
- It's **not mandatory** for fields to be byte-aligned.

---

## Index Format

Index of a field within the register.

```text
idx = [7:0]
idx = [31:16]
idx = [0:0]
```
- The `idx` must be within the range `[31:0]`.
- Overlapping between multiple fields in a register is not allowed.

---

## Software Access Types

Software access policy.

| `swacc` | Description |
|---------|---------|
| `na` | Reserved field |
| `r` | Read-only |
| `w` | Write-only |
| `rw` | Read/Write |
| `rclr` | Read clears all bits in field |
| `rset` | Read sets all bits in field |
| `w1clr` | Write 1 clears bit |
| `w1set` | Write 1 sets bit |
| `w1tog` | Write 1 toggles bit |
| `w1pul` | Write 1 generates 1-cycle pulse at bit |

---

## Hardware Access Types

Hardware access policy.

| `hwacc` | Meaning |
|---------|---------|
| `na` | No Hardware access |
| `r` | Hardware can Read-only |
| `w`| Hardware can Write-only |
| `rw` | Hardware can Read/Write |

---

## Valid SW-HW Access Combinations

The field type is determined by the SW and HW access policies set. The following field types are supported.

| S.No | Field Type | `swacc` | `hwacc` | Implementation | Comments |
|------|------------|----------|----------|----------------|----------|
| 1  | `RW`    | `rw`    | `na`       | Flop      | |
| 2  | `RWR`   | `rw`    | `r`        | Flop      | |
| 3  | `RWW`   | `rw`    | `w`        | Flop      | |
| 4  | `RW+`   | `rw`    | `rw`       | Flop      | |
| 5  | `RO`    | `r`     | `na`       | Const Net | `rstval` becomes the constant value driven. |
| 6  | `ROR`   | `r`     | `r`        | Const Net | `rstval` becomes the constant value driven. |
| 7  | `ROW`   | `r`     | `w`        | Net/Flop  | Field becomes Net if `hwctl = net`, otherwise Flop. |
| 8  | `RO+`   | `r`     | `rw`       | Flop      |  |
| 9  | `WO`    | `w`     | `na`       | -         | Must be used with `swevt` for meaningful application. Read as 0 by SW. |
| 10 | `WOR`   | `w`     | `r`        | Flop      | Read as 0 by SW. |
| 11 | `WO+`   | `w`     | `rw`       | Flop      | Read as 0 by SW. |
| 12 | `RSVD`  | `na`    | `na`       | -         | Read as 0 by SW. |
| 13 | `W1CLR` | `w1clr` | `w`/`rw`   | Flop      |  |
| 14 | `W1SET` | `w1set` | `w`/`rw`   | Flop      |  |
| 15 | `W1TOG` | `w1tog` | `w`/`rw`   | Flop      |  |
| 16 | `W1PUL` | `w1pul` | `r`        | Flop      | The `rstval` is overridden to 0. |
| 17 | `RCLR`  | `rclr`  | `w`/`rw`   | Flop      | Field is cleared after a successful SW read. |
| 18 | `RSET`  | `rset`  | `w`/`rw`   | Flop      | Field is set after a successful SW read. |

- Software writes have priority over Hardware writes.
- SW Write has no effect on the field value of SW read-only fields.
- SW Write has no effect on the field value of `RCLR/RSET` fields.
- SW Write 0 has no effect the field value of `W1*` fields.
- `W1*` fields have bitwise control from SW.

---

## Reset value Format

Reset value of the field. 

```text
rstval = 0x0
rstval = na
```
- The `rstval` must be in Hexa format.
- The `rstval = na` creates non-resettable flop, if the field is implemented as Flop.
- The `rstval` is mandatory for all field types **except** for-
	- `RO+/ROW` fields, if implemented as Nets.
	- `WO/W1PUL/RSVD` fields.

---

## Hardware Control Types

Describes how HW controls the HW writeable fields.

| `hwctl` | Description |
|---------|---------|
| `net` | HW continuously drives field |
| `wen` | HW drives write-data along with write-enable |
| `set `| Field-wise set signal from HW to set entire field |
| `clr` | Field-wise clear signal from HW to clear entire field |
| `tog` | Field-wise toggle signal from HW to toggle entire field |
| `setb` | Bit-wise set signal from HW |
| `clrb` | Bit-wise clear signal from HW |
| `togb` | Bit-wise toggle signal from HW |

- Mandatory to define `hwctl` when `hwacc = w` or `hwacc = rw`.
- The `hwctl` translates to input signals from HW in the Regblock for HW control.

---

## Software Events (swevt)

Software events generates a 1-cycle pulse to HW on SW reads/writes.

| `swevt` | Description |
|---------|---------|
| `na` | No event |
| `wtrig` | Pulse on write |
| `rtrig` | Pulse on read |
| `w1trig` | Pulse on writing 1 to bit; Bit-wise event |
| `w0trig` | Pulse on writing 0 to bit; Bit-wise event |

- Mandatory to define `swevt` for `WO` fields.
- The `swevt` translates to output signals to HW in the Regblock for HW control.

---

## Additional Notes

- Register width is fixed at 32 bits.
- APB byte strobes (PSTRB) are supported, PPROT, PSLVERR are not supported.
- If any CDC is required while interfacing with the HW, it should be done outside. RegForge doesn't support generating any CDC structures .
