from unicodedata import name
import serial
import time
import json
from datetime import datetime
import threading
import traceback 
import re
import yaml
import sys

# ser = serial.Serial(
#     port='COM3',\
#     baudrate=9600,\
#     parity=serial.PARITY_NONE,\
#     stopbits=serial.STOPBITS_ONE,\
#     bytesize=serial.EIGHTBITS,\
#         timeout=None)

class scan_name:
    def __init__(self, value="", inv=0, msb_index=0):
        self.value = value
        self.inv = inv # bits inversion 
        self.length = msb_index + 1 # bits inversion 

class reg_bits:
    def __init__(self, val_str="0", bitwidth=1, val_type="dec", inv=False):
        if bitwidth < 1:
            raise ValueError("Bitwidth must be at least 1")
        if int(val_str) < 0:
            raise ValueError("Decimal string must represent a non-negative integer")
        self.val_str = val_str
        self.bitwidth = bitwidth
        if val_type == "dec":
            if inv:
                self.binary_str = format(int(val_str), '0{}b'.format(bitwidth))[::-1]
            else:
                self.binary_str = format(int(val_str), '0{}b'.format(bitwidth))

        elif val_type == "bin":
            if len(val_str) != bitwidth:
                val_str = "0" * (bitwidth - len(val_str)) + val_str
            if inv:
                self.binary_str = val_str[::-1]
            else:
                self.binary_str = val_str

# offset needed in between
# TBD



# reg map here:
# defined strictly in order
# master scan, 18 bits

mscan_sel = "glb"
# mscan_sel = "vcal"
# mscan_sel = "readscan"
# mscan_sel = "glb"
# mscan_sel = "fcw"
# sub chain slection
mscan_enable_configscan =   reg_bits('00001', 5, 'bin') # little endian
mscan_enable_fcwscan =      reg_bits('00010', 5, 'bin')
# test = reg_bits('00010', 5, 'bin')
# print("test binary str: ", test.binary_str)
mscan_enable_readscan =     reg_bits('00100', 5, 'bin')
mscan_enable_vcalscan =     reg_bits('01000', 5, 'bin')
mscan_enable_glbscan =      reg_bits('10000', 5, 'bin')
mscan_bypass =              reg_bits('00000', 5, 'bin')
# clock to sub scan chains is off when bypass is 1
# glb scan chain control
mscan_glb_enable =          reg_bits('0', 1, 'dec')      # 1 bit
mscan_glb_inselect =        reg_bits('0', 1, 'dec')    # 1 bit
mscan_glb_outselect =       reg_bits('1', 1, 'dec')   # 1 bit
mscan_glb_control_bits = mscan_glb_enable.binary_str + mscan_glb_inselect.binary_str + mscan_glb_outselect.binary_str

# config scan chain control
# when outsel mux select is 1, the output is from the latched words (new inputs)
mscan_config_enable =       reg_bits('0', 1, 'dec')      # 1 bit
mscan_config_inselect =     reg_bits('1', 1, 'dec')    # 1 bit
mscan_config_outselect =    reg_bits('1', 1, 'dec')   # 1 bit
mscan_config_control_bits = mscan_config_enable.binary_str + mscan_config_inselect.binary_str + mscan_config_outselect.binary_str

# fcw scan chain control
mscan_fcw_enable =          reg_bits('0', 1, 'dec')      # 1 bit
mscan_fcw_inselect =        reg_bits('1', 1, 'dec')    # 1 bit
mscan_fcw_outselect =       reg_bits('1', 1, 'dec')   # 1 bit
mscan_fcw_control_bits = mscan_fcw_enable.binary_str + mscan_fcw_inselect.binary_str + mscan_fcw_outselect.binary_str

# vcal scan chain control
mscan_vcal_enable =         reg_bits('0', 1, 'dec')     # 1 bit
mscan_vcal_inselect =       reg_bits('1', 1, 'dec')     # 1 bit
mscan_vcal_outselect =      reg_bits('1', 1, 'dec')     # 1 bit
mscan_vcal_control_bits = mscan_vcal_enable.binary_str + mscan_vcal_inselect.binary_str + mscan_vcal_outselect.binary_str

# read scan chain control
mscan_read_inselect =       reg_bits('0', 1, 'dec').binary_str   # 1 bit

mscan_scanload =            reg_bits('0', 1, 'dec').binary_str        # 1 bit

# header of the mscan
mscan_header = ""

def select_mscan_header(mscan_sel):
     
    if (mscan_sel == "config"):
        return mscan_enable_configscan.binary_str
    elif (mscan_sel == "fcw"):
        return mscan_enable_fcwscan.binary_str
    elif (mscan_sel == "readscan"):
        return mscan_enable_readscan.binary_str
    elif (mscan_sel == "vcal"):
        return mscan_enable_vcalscan.binary_str
    elif (mscan_sel == "glb"):
        return mscan_enable_glbscan.binary_str
    else:
        return mscan_bypass.binary_str



    # More robust version that handles multiple formats
def extract_hex_string_robust(text):
    """
    Robust version that handles various formats and separators
    """
    # Pattern that allows for spaces, colons, commas, etc. in hex string
    header = "readback is ".encode('utf-8').hex()
    end = "endofstr".encode('utf-8').hex()
    pattern = r"readback is\s+([0-9A-Fa-f\s:,-]+?)\s*endofstr"
    if isinstance(text, str):
        print("Yes, it is a string")
    else:
        print("No, it is not a string!!!!!")
    match = re.search(pattern, text)

    if (match):
        # Clean up the extracted string - remove non-hex characters
        hex_string = re.sub(r'[^0-9A-Fa-f]', '', match.group(1))
        return hex_string if hex_string else None
    
    return None
    
# Alternative: Search directly in hex space
def extract_hex_direct_from_hex(input_hex):
    """
    Extract by converting keywords to hex and searching in hex space
    """
    # Convert keywords to hex
    start_hex = "readback is ".encode('utf-8').hex().upper()
    print("start_hex: ", start_hex)
    end_hex = "endofstr".encode('utf-8').hex().upper()
    print("end_hex: ", end_hex) 
    print("input_hex: ", input_hex)
    # Find positions in hex string
    start_pos = input_hex.upper().find(start_hex)
    if start_pos == -1:
        print("Start keyword not found")
        return None
    
    # Move past the start keyword
    data_start = start_pos + len(start_hex)
    
    # Find end keyword
    end_pos = input_hex.upper().find(end_hex, data_start)
    if end_pos == -1:
        print("End keyword not found")
        return None
    
    # Extract the hex data between keywords
    hex_data = input_hex[data_start:end_pos]
    print("hex data before clean: ", hex_data)
    # Clean up - remove any non-hex characters that might be in the hex string
    hex_data_clean = re.sub(r'[^0-9A-Fa-f]', '', hex_data)
    print("hex_data_clean: ", hex_data_clean)
    return hex_data_clean if hex_data_clean else None

def extract_bin_from_hex_string(hex_string):
    ext_hex_readback = extract_hex_direct_from_hex(hex_string)
    print("Extracted hex string is: " + (ext_hex_readback))
    if isinstance(ext_hex_readback, str):
        print("Yes, it is a string")
    ext_bin_readback = bin(int(bytes.fromhex(ext_hex_readback).decode('utf-8', errors='replace'), 16))[2:]
    ext_bin_readback = ''.join([chr(int(ext_hex_readback[i:i+2], 16)) for i in range(0, len(ext_hex_readback), 2)])
    return ext_bin_readback


def form_sent_string(scan_enable, scan_bypass, mscan_header, sub_chain_control_bits, sub_scan_data_bits):
    """form the full mscan string to be sent out and return as hex data string"""
    scan_complete = mscan_header + sub_chain_control_bits + sub_scan_data_bits
    scan_complete_str, last_byte_offset = binary_to_string_safe(scan_complete[::-1])
    control_byte = form_control_byte(scan_enable, scan_bypass, num_of_bits=last_byte_offset)
    control_byte_hex, num = binary_to_string_safe(control_byte)

    full_sent_string = control_byte_hex + scan_complete_str
    return full_sent_string

    
# print("mscan_sel: ", mscan_sel)
# select_mscan_header(mscan_sel)
# print("mscan_header: ", mscan_header)
# select_mscan_header("config")
# print("mscan_header: ", mscan_header)

def update_mscan_complete(mscan_sel):
    global mscan_complete
    select_mscan_header(mscan_sel)
    mscan_complete = mscan_header + mscan_glb_control_bits + mscan_config_control_bits + mscan_fcw_control_bits + mscan_vcal_control_bits + mscan_read_inselect + mscan_scanload 
    return mscan_complete

# change the header here for mscan complete
mscan_complete = update_mscan_complete("glb")
# print("mscan_complete length: ", len(mscan_complete))
# print("mscan_complete: ", mscan_complete)

# glb scan reg_bits definition
CLKF_bits =         reg_bits( '0' * 16 + '01011' + '0000000000' + '0' * 23, 54, 'bin') # 54 bits
CLKHD_bits =        reg_bits('3', 2, 'dec') # 2 bits
CLKOD_bits =        reg_bits('1', 11, 'dec') # 11 bits
PWRDN_bits = reg_bits('0', 1, 'dec') # 1 bit
BYPASS_bits = reg_bits('0', 1, 'dec') # 1 bit
BYPASS_NLK_ENB_bits = reg_bits('0', 1, 'dec') # 1 bit
TEST_MODE_bits = reg_bits('0', 1, 'dec') # 1 bit
TESTSEL_bits = reg_bits('0', 3, 'dec') # 3 bits
LOWFNACC_bits = reg_bits('0', 1, 'dec')
NOFNACC_bits = reg_bits('0', 1, 'dec')
PGAIN_LGMLT_bits = reg_bits('1', 6, 'dec')
IGAIN_LGMLT_bits = reg_bits('111011', 6, 'bin')
IPGAIN_LGMLT_bits = reg_bits('1', 6, 'dec')
IIGAIN_LGMLT_bits = reg_bits('111011', 6, 'bin')
IBW_NLK_ENB_bits = reg_bits('1', 1, 'dec')
LOCK_TYPE_bits = reg_bits('0', 1, 'dec')
LOCK_SEL_bits = reg_bits('8', 4, 'dec')
FBSEL_bits = reg_bits('1', 1, 'dec')
VCOCAL_RDIV_LGFCT_bits = reg_bits('4', 3, 'dec')
VCOCAL_OFFBYP_bits = reg_bits('1', 1, 'dec')
VCOCAL_ENB_bits = reg_bits('1', 1, 'dec')
BIAS_REF_SEL_bits = reg_bits('4', 3, 'dec')
REG_EXT_SEL1 = reg_bits('0', 1, 'dec')
REG_TEST_SEL1 = reg_bits('0', 1, 'dec')
REG_TEST_REP1 = reg_bits('0', 1, 'dec')
REG_TEST_OUT1 = reg_bits('0', 1, 'dec')
REG_TEST_DRV1 = reg_bits('0', 1, 'dec')
REG_RESET1 = reg_bits('0', 1, 'dec')
REG_PWRDN1 = reg_bits('0', 1, 'dec')
BG_RESET1 = reg_bits('0', 1, 'dec')
BG_PWRDN1 = reg_bits('0', 1, 'dec')
REG_EXT_SEL2 = reg_bits('0', 1, 'dec')
REG_TEST_SEL2 = reg_bits('1', 1, 'dec')
REG_TEST_REP2 = reg_bits('0', 1, 'dec')
REG_TEST_OUT2 = reg_bits('1', 1, 'dec')
REG_TEST_DRV2 = reg_bits('0', 1, 'dec')
REG_RESET2 = reg_bits('0', 1, 'dec')
REG_PWRDN2 = reg_bits('0', 1, 'dec')
BG_RESET2 = reg_bits('0', 1, 'dec')
BG_PWRDN2 = reg_bits('0', 1, 'dec')
RSTFNACC_bits = reg_bits('0', 1, 'dec')
MAX_VCO_BIAS_bits = reg_bits('0', 1, 'dec')
VCOCAL_OFF_bits = reg_bits('11', 5, 'dec')

# concat glb reg bits
# print("CLKF_bits, non-global: ", CLKF_bits.binary_str)
glb_complete = CLKF_bits.binary_str + \
            CLKHD_bits.binary_str + \
            CLKOD_bits.binary_str + \
            PWRDN_bits.binary_str + \
            BYPASS_bits.binary_str + \
            BYPASS_NLK_ENB_bits.binary_str + \
            TEST_MODE_bits.binary_str + \
            TESTSEL_bits.binary_str + \
            LOWFNACC_bits.binary_str + \
            NOFNACC_bits.binary_str + \
            PGAIN_LGMLT_bits.binary_str + \
            IGAIN_LGMLT_bits.binary_str + \
            IPGAIN_LGMLT_bits.binary_str + \
            IIGAIN_LGMLT_bits.binary_str + \
            IBW_NLK_ENB_bits.binary_str + \
            LOCK_TYPE_bits.binary_str + \
            LOCK_SEL_bits.binary_str + \
            FBSEL_bits.binary_str + \
            VCOCAL_RDIV_LGFCT_bits.binary_str + \
            VCOCAL_OFFBYP_bits.binary_str + \
            VCOCAL_ENB_bits.binary_str + \
            BIAS_REF_SEL_bits.binary_str + \
            REG_EXT_SEL1.binary_str + \
            REG_TEST_SEL1.binary_str + \
            REG_TEST_REP1.binary_str + \
            REG_TEST_OUT1.binary_str + \
            REG_TEST_DRV1.binary_str + \
            REG_RESET1.binary_str + \
            REG_PWRDN1.binary_str + \
            BG_RESET1.binary_str + \
            BG_PWRDN1.binary_str + \
            REG_EXT_SEL2.binary_str + \
            REG_TEST_SEL2.binary_str + \
            REG_TEST_REP2.binary_str + \
            REG_TEST_OUT2.binary_str + \
            REG_TEST_DRV2.binary_str + \
            REG_RESET2.binary_str + \
            REG_PWRDN2.binary_str + \
            BG_RESET2.binary_str + \
            BG_PWRDN2.binary_str + \
            RSTFNACC_bits.binary_str + \
            MAX_VCO_BIAS_bits.binary_str + \
            VCOCAL_OFF_bits.binary_str
print("glb_complete length: ", len(glb_complete)) 


glb_complete_reset = CLKF_bits.binary_str + \
            CLKHD_bits.binary_str + \
            CLKOD_bits.binary_str + \
            PWRDN_bits.binary_str + \
            BYPASS_bits.binary_str + \
            BYPASS_NLK_ENB_bits.binary_str + \
            TEST_MODE_bits.binary_str + \
            TESTSEL_bits.binary_str + \
            LOWFNACC_bits.binary_str + \
            NOFNACC_bits.binary_str + \
            PGAIN_LGMLT_bits.binary_str + \
            IGAIN_LGMLT_bits.binary_str + \
            IPGAIN_LGMLT_bits.binary_str + \
            IIGAIN_LGMLT_bits.binary_str + \
            IBW_NLK_ENB_bits.binary_str + \
            LOCK_TYPE_bits.binary_str + \
            LOCK_SEL_bits.binary_str + \
            FBSEL_bits.binary_str + \
            VCOCAL_RDIV_LGFCT_bits.binary_str + \
            VCOCAL_OFFBYP_bits.binary_str + \
            VCOCAL_ENB_bits.binary_str + \
            BIAS_REF_SEL_bits.binary_str + \
            REG_EXT_SEL1.binary_str + \
            REG_TEST_SEL1.binary_str + \
            REG_TEST_REP1.binary_str + \
            REG_TEST_OUT1.binary_str + \
            REG_TEST_DRV1.binary_str + \
            '1000' + \
            REG_EXT_SEL2.binary_str + \
            REG_TEST_SEL2.binary_str + \
            REG_TEST_REP2.binary_str + \
            REG_TEST_OUT2.binary_str + \
            REG_TEST_DRV2.binary_str + \
            '1000' + \
            RSTFNACC_bits.binary_str + \
            MAX_VCO_BIAS_bits.binary_str + \
            VCOCAL_OFF_bits.binary_str

glb_complete_bgpwrdn = CLKF_bits.binary_str + \
            CLKHD_bits.binary_str + \
            CLKOD_bits.binary_str + \
            PWRDN_bits.binary_str + \
            BYPASS_bits.binary_str + \
            BYPASS_NLK_ENB_bits.binary_str + \
            TEST_MODE_bits.binary_str + \
            TESTSEL_bits.binary_str + \
            LOWFNACC_bits.binary_str + \
            NOFNACC_bits.binary_str + \
            PGAIN_LGMLT_bits.binary_str + \
            IGAIN_LGMLT_bits.binary_str + \
            IPGAIN_LGMLT_bits.binary_str + \
            IIGAIN_LGMLT_bits.binary_str + \
            IBW_NLK_ENB_bits.binary_str + \
            LOCK_TYPE_bits.binary_str + \
            LOCK_SEL_bits.binary_str + \
            FBSEL_bits.binary_str + \
            VCOCAL_RDIV_LGFCT_bits.binary_str + \
            VCOCAL_OFFBYP_bits.binary_str + \
            VCOCAL_ENB_bits.binary_str + \
            BIAS_REF_SEL_bits.binary_str + \
            REG_EXT_SEL1.binary_str + \
            REG_TEST_SEL1.binary_str + \
            REG_TEST_REP1.binary_str + \
            REG_TEST_OUT1.binary_str + \
            REG_TEST_DRV1.binary_str + \
            '0101' + \
            REG_EXT_SEL2.binary_str + \
            REG_TEST_SEL2.binary_str + \
            REG_TEST_REP2.binary_str + \
            REG_TEST_OUT2.binary_str + \
            REG_TEST_DRV2.binary_str + \
            '0101' + \
            RSTFNACC_bits.binary_str + \
            MAX_VCO_BIAS_bits.binary_str + \
            VCOCAL_OFF_bits.binary_str
        

# print("the length of glb_complete: ", len(glb_complete))
# print("the length of glb_complete_reset: ", len(glb_complete_reset))


# design vairbale value
# sz_gm_log_int = 7
# config scan chain bits

# grab the cut and pasted content, identify the variable name and bit length, format default value assignment in the string, ignore + signs
config_en_alpha_dynb =          reg_bits('1',   1,    'dec')
config_byp_rs_en =              reg_bits('1',   1,    'dec')
sync_load =                     reg_bits('1',   1,    'dec')
config_gm_log_en =              reg_bits('0',   1,    'dec') 
config_fixed_zt_en =            reg_bits('0',   1,    'dec')
en_roundup =                    reg_bits('1',   1,    'dec')
config_gm_log_int_init_en =     reg_bits('1',   1,    'dec')
config_fp_len_en =              reg_bits('1',   1,    'dec')
config_bwr_max_lg =             reg_bits('10',   11,   'dec') # 11 bits double check the default value ??????
# print(len(config_bwr_max_lg))     
config_bwr_lg =                 reg_bits('10',   11,   'dec') # 11 bits double check the default value ??????
config_alphars_norm =           reg_bits('20',   11,   'dec') # 11 bits double check the default value ??????
config_alphars_pert =           reg_bits('20',   11,   'dec') # 11 bits double check the default value ??????
# print(config_alphars_norm.binary_str) 
config_fp_len =                 reg_bits('22',   7,    'dec') # 7 bits double check the default value ??????
config_gm_log_int_init =        reg_bits('50',   7,    'dec') # 7 bit double check the default value ??????
config_gm_log_int =             reg_bits('25',   7,    'dec') # 7 bit double check the default value ??????
config_gmlg_maxint =            reg_bits('52',   7,    'dec') # 7 bit double check the default value ??????
config_gmlg_minint =            reg_bits('0',   7,    'dec') # 7 bit double check the default value ??????
config_fi_log =                 reg_bits('2048',   16,   'dec') # 16 bits double check the default value ??????
config_fd_log =                 reg_bits('2048',   16,   'dec') # 16 bits double check the default value ??????
config_fullbw_gm_lg =           reg_bits('32',   8,    'dec') # 8 bit double check the default value ??????
config_fullbw_gm_lg_offset =    reg_bits('4',   8,    'dec') # 8 bit double check the default value ??????
config_rs_cnt_thres_dft =       reg_bits('127',   18,   'dec')  # 8 bit double check the default value ??????
config_rs_init =                reg_bits('0',   8,    'dec')  # 8 bit double check the default value ??????
config_rs_dec =                 reg_bits('1',   8,    'dec')   # 8 bit double check the default value ??????
config_rs_inc =                 reg_bits('1',   8,    'dec')   # 8 bit double check the default value ??????
config_rs_max =                 reg_bits('11',   8,    'dec')   # 8 bit double check the default value ??????
config_rs_min =                 reg_bits('0',   8,    'dec')   # 8 bit double check the default value ??????
config_rs_val =                 reg_bits('15',   8,    'dec')   # 8 bit double check the default value ??????
config_fixed_zt =               reg_bits('0',   7,    'dec') # 7 bit double check the default value ??????
config_zt_max =                 reg_bits('5',   7,    'dec') # 7 bit double check the default value ??????
config_ifcw_init_lg =           reg_bits('5',   7,    'dec') # 7 bit double check the default value ??????
config_slip_halt_threslg =      reg_bits('6',   4,    'dec') # 4 bit double check the default value ??????
config_prop_init =              reg_bits('30',   7,    'dec') # 7 bit double check the default value ??????
config_cnst_max_iupd =          reg_bits('38',   7,    'dec') # 7 bit double check the default value ??????
config_cnst_min_iupd =          reg_bits('1',   7,    'dec') # 7 bit double check the default value ??????
config_cnst_max_pupd =          reg_bits('41',   7,    'dec') # 7 bit double check the default value ??????
config_cnst_min_pupd =          reg_bits('1',   7,    'dec') # 7 bit double check the default value ??????
config_cnst_max_slip_iupd =     reg_bits('45',   7,    'dec') # 7 bit double check the default value ??????
config_fp_len_slip =            reg_bits('22',   7,    'dec')  # 7 bit double check the default value ??????
config_lpfltr_dly =             reg_bits('8',   8,    'dec')  # 8 bit double check the default value ??????
config_slip_guard =             reg_bits('127',   7,    'dec')  # 7 bit double check the default value ??????
config_slip_guard_iupd =        reg_bits('1',   7,    'dec')      # 7 bit double check the default value ??????
config_cnst_nominal_nf_lg =     reg_bits('4',   6,    'dec')  # 6 bit double check the default value ??????
config_snapshot_cnt_thres =     reg_bits('8188',   13,   'dec') # 13 bit double check the default value ??????
rs_mask_en =                    reg_bits('0',   1,    'dec')
rs_settling_plateau_en =        reg_bits('1',   1,    'dec')
config_rs_mask =                reg_bits('3',   8,    'dec')  # 8 bit double check the default value ??????
config_slip_rs_reset_en =       reg_bits('1',   1,    'dec')
config_rs_reset_threshold =     reg_bits('8',   8,    'dec') # 8 bit double check the default value ??????
config_rs_settling_plateau =    reg_bits('11',   8,    'dec') # 8 bit double check the default value ??????
config_ip_diff =                reg_bits('1',   7,    'dec') # 7 bit double check the default value ??????
config_rs_sp_state_code =       reg_bits('32',   6,    'dec') # 6 bit double check the default value ??????
config_rs_sp_mask =             reg_bits('4',   8,    'dec') # 8 bit double check the default value ??????
config_rs_mask_sval =           reg_bits('8',   8,    'dec') # 8 bit double check the default value ??????

# concat config reg bits
config_complete = config_en_alpha_dynb.binary_str + \
config_byp_rs_en.binary_str + \
sync_load.binary_str + \
config_gm_log_en.binary_str + \
config_fixed_zt_en.binary_str + \
en_roundup.binary_str + \
config_gm_log_int_init_en.binary_str + \
config_fp_len_en.binary_str + \
config_bwr_max_lg.binary_str + \
config_bwr_lg.binary_str + \
config_alphars_norm.binary_str + \
config_alphars_pert.binary_str + \
config_fp_len.binary_str + \
config_gm_log_int_init.binary_str + \
config_gm_log_int.binary_str + \
config_gmlg_maxint.binary_str + \
config_gmlg_minint.binary_str + \
config_fi_log.binary_str + \
config_fd_log.binary_str + \
config_fullbw_gm_lg.binary_str + \
config_fullbw_gm_lg_offset.binary_str + \
config_rs_cnt_thres_dft.binary_str + \
config_rs_init.binary_str + \
config_rs_dec.binary_str + \
config_rs_inc.binary_str + \
config_rs_max.binary_str + \
config_rs_min.binary_str + \
config_rs_val.binary_str + \
config_fixed_zt.binary_str + \
config_zt_max.binary_str + \
config_ifcw_init_lg.binary_str + \
config_slip_halt_threslg.binary_str + \
config_prop_init.binary_str + \
config_cnst_max_iupd.binary_str + \
config_cnst_min_iupd.binary_str + \
config_cnst_max_pupd.binary_str + \
config_cnst_min_pupd.binary_str + \
config_cnst_max_slip_iupd.binary_str + \
config_fp_len_slip.binary_str + \
config_lpfltr_dly.binary_str + \
config_slip_guard.binary_str + \
config_slip_guard_iupd.binary_str + \
config_cnst_nominal_nf_lg.binary_str + \
config_snapshot_cnt_thres.binary_str + \
rs_mask_en.binary_str + \
rs_settling_plateau_en.binary_str + \
config_rs_mask.binary_str + \
config_slip_rs_reset_en.binary_str + \
config_rs_reset_threshold.binary_str + \
config_rs_settling_plateau.binary_str + \
config_ip_diff.binary_str + \
config_rs_sp_state_code.binary_str + \
config_rs_sp_mask.binary_str + \
config_rs_mask_sval.binary_str
print("config_complete length: ", len(config_complete))

config_complete_reset = config_en_alpha_dynb.binary_str + \
config_byp_rs_en.binary_str + \
'0' + \
config_gm_log_en.binary_str + \
config_fixed_zt_en.binary_str + \
en_roundup.binary_str + \
config_gm_log_int_init_en.binary_str + \
config_fp_len_en.binary_str + \
config_bwr_max_lg.binary_str + \
config_bwr_lg.binary_str + \
config_alphars_norm.binary_str + \
config_alphars_pert.binary_str + \
config_fp_len.binary_str + \
config_gm_log_int_init.binary_str + \
config_gm_log_int.binary_str + \
config_gmlg_maxint.binary_str + \
config_gmlg_minint.binary_str + \
config_fi_log.binary_str + \
config_fd_log.binary_str + \
config_fullbw_gm_lg.binary_str + \
config_fullbw_gm_lg_offset.binary_str + \
config_rs_cnt_thres_dft.binary_str + \
config_rs_init.binary_str + \
config_rs_dec.binary_str + \
config_rs_inc.binary_str + \
config_rs_max.binary_str + \
config_rs_min.binary_str + \
config_rs_val.binary_str + \
config_fixed_zt.binary_str + \
config_zt_max.binary_str + \
config_ifcw_init_lg.binary_str + \
config_slip_halt_threslg.binary_str + \
config_prop_init.binary_str + \
config_cnst_max_iupd.binary_str + \
config_cnst_min_iupd.binary_str + \
config_cnst_max_pupd.binary_str + \
config_cnst_min_pupd.binary_str + \
config_cnst_max_slip_iupd.binary_str + \
config_fp_len_slip.binary_str + \
config_lpfltr_dly.binary_str + \
config_slip_guard.binary_str + \
config_slip_guard_iupd.binary_str + \
config_cnst_nominal_nf_lg.binary_str + \
config_snapshot_cnt_thres.binary_str + \
rs_mask_en.binary_str + \
rs_settling_plateau_en.binary_str + \
config_rs_mask.binary_str + \
config_slip_rs_reset_en.binary_str + \
config_rs_reset_threshold.binary_str + \
config_rs_settling_plateau.binary_str + \
config_ip_diff.binary_str + \
config_rs_sp_state_code.binary_str + \
config_rs_sp_mask.binary_str + \
config_rs_mask_sval.binary_str
# print("config_complete length: ", len(config_complete))



# def update_all_config_scan_bits(**kwargs):
    


# scan read reg_bits definition
chip_id =                       reg_bits('0',   10,     'dec') # 8 bits
config_out_fcw_transient =      reg_bits('0',   52,     'dec') # 1 bit
eavg_norm =                     reg_bits('0',   28,     'dec') # 16 bits
eavg_pert =                     reg_bits('0',   28,     'dec') # 16 bits
int_upd0 =                      reg_bits('0',   52,     'dec') # 16 bits
prop_upd0 =                     reg_bits('0',   52,     'dec') # 16 bits
gm_log_int_ff =                 reg_bits('0',   7,      'dec') # 7 bits
rs_ff =                         reg_bits('0',   8,      'dec') # 8 bits
scan_out_zt =                   reg_bits('0',   7,      'dec') # 7 bits

readout_complete = chip_id.binary_str + \
config_out_fcw_transient.binary_str + \
eavg_norm.binary_str + \
eavg_pert.binary_str + \
int_upd0.binary_str + \
prop_upd0.binary_str + \
gm_log_int_ff.binary_str + \
rs_ff.binary_str + \
scan_out_zt.binary_str

# fcw scan reg_bits definition
# fcw_scan = reg_bits( '011'+ '11' + '11111'  + '1' * 31, 41, 'bin', inv=True) # 41 bits
# fcw_scan = reg_bits( '0' * 31 + '00000' + '00000', 41, 'bin', inv=False) # 41 bits
fcw_scan = reg_bits( '1' * 41 , 41, 'bin', inv=False) # 41 bits


print("fcw_scan length: ", len(fcw_scan.binary_str))

# vcal scan reg_bits definition
vcal_scan = reg_bits('0', 5, 'dec') # 5 bits
print("vcal_scan length: ", len(vcal_scan.binary_str))

# concat readout bits for size checking
scanread_complete = chip_id.binary_str + \
config_out_fcw_transient.binary_str + \
eavg_norm.binary_str + \
eavg_pert.binary_str + \
int_upd0.binary_str + \
prop_upd0.binary_str + \
gm_log_int_ff.binary_str + \
rs_ff.binary_str + \
scan_out_zt.binary_str

scanread_complete = '10' * 122

# print("scanread_complete length: ", len(scanread_complete))
# concat

# size of each scan chian (rtl design)
#   GLBSCAN 140 bits [139:0]
#   MSCAN 19 bits [18:0]
#   SCAN_READ 244 bits [243:0]
#   FCW_SCAN 41 bits [40:0] # inverted
#   VCAL_SCAN 5 bits [4:0] # inverted
#   CONFIG_SCAN 372 bits [371:0]
master_scan = scan_name(mscan_complete, 0, 18)
# print(master_scan.length)
config_scan = scan_name("", 0, 371)
scan_read = scan_name("", 0, 243)
# fcw_scan = scan_name("", 0, 40)
vacal_scan = scan_name("", 0, 4)
glb_scan = scan_name("", 0, 139)

def invert_binary_string(bin_str): # bitwise invert of a binary string
    inverted = ''.join('1' if bit == '0' else '0' for bit in bin_str)
    return inverted

# last_byte = "00110101" 
# last_byte_inv = invert_binary_string(last_byte)
# print(last_byte_inv)
# control_stream = "00110101" + last_byte + last_byte * 2 + "0101"
# control_stream = "00110101" + "01010101"+ "010" + "00100" + "00110101" + "01010100" + "010"
# control_stream = "00110001" + "01010100" + "000"

# control_stream = "00110101" + "01010101"+ "010" 
# control_stream = "01111101" * 15

def hex_to_binary(hex_string, pad_zeros=False):
    """
    Convert hex string to binary string.
    
    Parameters:
    hex_string (str): Input hex string
    pad_zeros (bool): If True, pad with leading zeros to full width
    
    Returns:
    str: Binary string representation
    """
    try:
        # Remove any '0x' prefix if present
        if hex_string.startswith(('0x', '0X')):
            hex_string = hex_string[2:]
        
        if pad_zeros:
            # Pad to full width (each hex digit = 4 bits)
            num_bits = len(hex_string) * 4
            binary_string = format(int(hex_string, 16), f'0{num_bits}b')
        else:
            # Convert without padding (no leading zeros)
            binary_string = format(int(hex_string, 16), 'b')
        
        return binary_string
    
    except ValueError as e:
        raise ValueError(f"Invalid hex string: {hex_string}") from e

# import default value and order list from yaml file
def load_from_yaml(path):
    try:
        with open(path, 'r') as file:
            data = yaml.safe_load(file)
            order_list = data.get('concat_order', [])
            default_values = data.get('default_values', {})
            bits_lengths = data.get('bits_length', {})
            default_formats = data.get('default_format', {})
            return order_list, default_values, bits_lengths, default_formats
    except Exception as e:
        print(f"Error loading YAML file: {e}")
        return None

# takes in update in the form of:
# update_glb_scan_string(CLKF_bits=CLKF_bits)

def update_scan_string(yaml_path, **kwargs):
    order_list, default_values, bits_lengths, default_formats = load_from_yaml(yaml_path)
    # print("default_values:")
    # print(default_values)
    # print("order_list:")
    # print(order_list)
    # print("kwargs:")
    # print(kwargs)

    replacement_var_list = []
    if kwargs:
        for name, obj in kwargs.items():
            if name not in order_list:
                print(f"Error: {name} not found in order_list. Please check the variable name.")
            replacement_var_list.append(name)

    
    glb_scan_str = ''
    for index, var_name in enumerate(order_list):
        if (var_name) not in replacement_var_list:
            # print(var_name)
            temp = reg_bits(default_values[index][var_name], bits_lengths[index][var_name], default_formats[index][var_name])
            # total_str_len += bits_lengths[index][var_name]
            glb_scan_str += temp.binary_str
            # print("var_name not in replacement_var_list: ", var_name)
            # print("length: ", bits_lengths[index][var_name])
        else:
            # total_str_len += len(kwargs[var_name].binary_str)
            # print("var_name in replacement_var_list: ", var_name)
            # print("length: ", len(kwargs[var_name].binary_str))
        #    print(kwargs[var_name].binary_str)
            glb_scan_str += kwargs[var_name].binary_str 

    # print("Total glb scan string length: ")
    # print(total_str_len)
    return glb_scan_str

def update_all_glb_scan_bits(**kwargs):
    # update the main glb value
    glb_complete_local = update_scan_string(yaml_path='glb.yaml', **kwargs)
    print(glb_complete_local)

    kwargs['REG_RESET1'] = reg_bits('1', 1, 'dec')
    kwargs['REG_PWRDN1'] = reg_bits('0', 1, 'dec')
    kwargs['BG_RESET1'] = reg_bits('0', 1, 'dec') 
    kwargs['BG_PWRDN1'] = reg_bits('0', 1, 'dec')   

    kwargs['REG_RESET2'] = reg_bits('1', 1, 'dec')
    kwargs['REG_PWRDN2'] = reg_bits('0', 1, 'dec')
    kwargs['BG_RESET2'] = reg_bits('0', 1, 'dec') 
    kwargs['BG_PWRDN2'] = reg_bits('0', 1, 'dec') 
    
    # update the reset glb value
    glb_complete_reset_local = update_scan_string(yaml_path='glb.yaml', **kwargs)
    print(glb_complete_reset_local)

    
    kwargs['REG_RESET1'] = reg_bits('0', 1, 'dec')
    kwargs['REG_PWRDN1'] = reg_bits('1', 1, 'dec')
    kwargs['BG_RESET1'] = reg_bits('0', 1, 'dec') 
    kwargs['BG_PWRDN1'] = reg_bits('1', 1, 'dec')   

    kwargs['REG_RESET2'] = reg_bits('0', 1, 'dec')
    kwargs['REG_PWRDN2'] = reg_bits('1', 1, 'dec')
    kwargs['BG_RESET2'] = reg_bits('0', 1, 'dec') 
    kwargs['BG_PWRDN2'] = reg_bits('1', 1, 'dec') 
    print(kwargs)
    # update the bgpwrdn glb value
    glb_complete_bgpwrdn_local = update_scan_string(yaml_path='glb.yaml', **kwargs)
    print(glb_complete_bgpwrdn_local)

    return glb_complete_local, glb_complete_reset_local, glb_complete_bgpwrdn_local

def update_all_config_scan_bits(**kwargs):
    # update the main config value
    config_complete_local = update_scan_string(yaml_path='config.yaml', **kwargs)
    # print(config_complete_local)

    kwargs['sync_load'] = reg_bits('0', 1, 'dec')

    # update the reset config value
    config_complete_reset_local = update_scan_string(yaml_path='config.yaml', **kwargs)
    # print(config_complete_reset_local)

    return config_complete_local, config_complete_reset_local


# call this script to execute the power on sequence
def power_on(comm, config_data_bits, config_data_bits_reset, glb_data_bits, glb_data_bits_reset, glb_data_bits_bgpwrdn):

    # write init value into config scan chain
    mscan_writer_only(comm, mscan_sel="config", glb_control_bits="011", config_control_bits="011", fcw_control_bits="011", readout_control_bits="0", vcal_control_bits="000", scan_load_1bit="0", mode="reset", data_bits=config_data_bits_reset)

    # glb power down
    mscan_writer_only(comm, mscan_sel="glb", glb_control_bits="011", config_control_bits="000", fcw_control_bits="011", readout_control_bits="0",  vcal_control_bits="000", scan_load_1bit="0", mode="bgpwrdn",data_bits=glb_data_bits_bgpwrdn)

    # glb power on
    mscan_writer_only(comm, mscan_sel="glb", glb_control_bits="011", config_control_bits="000", fcw_control_bits="011", readout_control_bits="0", vcal_control_bits="000", scan_load_1bit="0", mode="normal", data_bits=glb_data_bits)

    # glb reset 
    mscan_writer_only(comm, mscan_sel="glb", glb_control_bits="011", config_control_bits="000", fcw_control_bits="011", readout_control_bits="0", vcal_control_bits="000", scan_load_1bit="0", mode="reset", data_bits=glb_data_bits_reset)

    # glb release reset
    mscan_writer_only(comm, mscan_sel="glb", glb_control_bits="011", config_control_bits="000", fcw_control_bits="011", readout_control_bits="0", vcal_control_bits="000", scan_load_1bit="0", mode="normal", data_bits=glb_data_bits)


def control_reset_release(comm, config_data_bits, config_data_bits_reset):

    # config reset
    # relaease controller reset
    mscan_writer_only(comm, mscan_sel="config", glb_control_bits="011", config_control_bits="011", fcw_control_bits="000", readout_control_bits="0", vcal_control_bits="000", scan_load_1bit="0", mode="reset", data_bits=config_data_bits_reset)

    # relaease controller reset
    mscan_writer_only(comm, mscan_sel="config", glb_control_bits="011", config_control_bits="011", fcw_control_bits="000", readout_control_bits="0", vcal_control_bits="000", scan_load_1bit="0", mode="reset", data_bits=config_data_bits)

def glb_writer_after_por(comm, glb_data_bits):
    mscan_writer_only(comm, mscan_sel="glb", glb_control_bits="011", config_control_bits="000", fcw_control_bits="000", readout_control_bits="0", vcal_control_bits="000", scan_load_1bit="0", mode="normal", data_bits=glb_data_bits)

def readout(comm):
    readout_scan_read(comm, mscan_sel="readscan", glb_control_bits="011", config_control_bits="000", fcw_control_bits="000", readout_control_bits="1", vcal_control_bits="000", scan_load_1bit="0")


# CLKF_bits =         reg_bits( '0' * 16 + '10011' + '0000000000' + '0' * 23, 54, 'bin') # 54 bits
# print(update_glb_scan_string(CLKF_bits=CLKF_bits))
# print("Length of updated glb scan string: ", len(update_glb_scan_string(CLKF_bits=CLKF_bits)))

def select_subchain(mscan_sel, mode=False):
    # select and update sub chain strings
    if (mscan_sel == "config"):
        if (mode == "reset"):
            return config_complete_reset
        else:
            return config_complete
    elif (mscan_sel == "fcw"):
        return fcw_scan.binary_str
    elif (mscan_sel == "readscan"):
        return readout_complete
    elif (mscan_sel == "vcal"):
        return vcal_scan.binary_str
    elif (mscan_sel == "glb"):
        if mode == "reset":
            return glb_complete_reset
        elif (mode == "normal" ):
            return glb_complete
        elif (mode == "bgpwrdn" ):
            return glb_complete_bgpwrdn
    elif (mscan_sel == "bypass"):
        return ""
    else:
        return ""

# define the write mode
# The scan chain is flushed in the following order:
# 1) turn off scan_bypass signal (this will bypass all the sub scan chains)
# 2) write to glb scan chain to select the desired sub scan chain by changing the mscansel bits

def write_initiator(obj):
    if obj.ser and obj.ser.is_open:
        print("Starting write mode...")
        # send the control stream
        obj.send_data("\n")
        print("Control stream sent.")
    else:
        print("Serial port is not open. Cannot enter write mode.")

latch_hold = '1'
latch_transparent = '0'

test_var = 1

def change_test_var_to_zero():
    global test_var
    test_var = 0
    return test_var

# print("Before change_test_var_to_zero, test_var =", test_var)
# change_test_var_to_zero()
# print("After change_test_var_to_zero, test_var =", test_var)


# control byte, forming 

def form_control_byte(scan_enable, scan_bypass, num_of_bits): # add other control bits later if needed
    control_byte = ''
    if (num_of_bits > 1024):
        print("Error: num_of_bits exceeds 1024 bits limit.")
        return None
    # the first four bits are reserved for last byte offset
    control_byte += format(num_of_bits, '012b')
    control_byte += '00'
    # scan_enable bit
    if scan_enable:
        control_byte += '1'
    else:
        control_byte += '0'
    
    # scan_bypass bit
    if scan_bypass:
        control_byte += '1'
    else:
        control_byte += '0'    
    return control_byte

# quick debug lines
# control_byte = reg_bits(form_control_byte(scan_enable=1, scan_bypass=1), 8, 'bin')
# print("Control byte: ", control_byte.binary_str)

def uart_recv_confirmation(recv_bytes, termination_str="\n\r\n\r"):
    if (termination_str not in recv_bytes):
        return False    # keep waiting
    return True



def write_mode():
    # open serial port 
    comm = AdvancedMicroBlazeComm(port='COM3', baudrate=9600)  # make port connection
    if comm.connect():
        # send scan_en, scan_bypass signal before any data
        comm.send_data()
        
    else:
        print("Failed to connect.")

# print("connect to: " + ser.portstr)
# f = open("com_port_debug.txt", "w")w
# encoding = 'utf-8'
# count_limit = 10000000000
# count = 0
# while count < count_limit:
#     # print (ser.readline())
#     count = count + 1
#     if ser.in_waiting:  # Check if data is available
#         line = ser.readline().decode('utf-8').strip()
#         if line:  # Only process non-empty lines
#             print(line)
#             # print(isinstance(line, str))
#             f.write(line + '\n')


# f.close()
# ser.close()






# handling the conversion to 
def binary_to_string_safe(binary_string):
    try:
        # Remove any spaces or non-binary characters
        clean_binary = ''.join(filter(lambda x: x in '01', binary_string))
        len_binary = len(clean_binary)
        # Ensure length is multiple of 8
        if len(clean_binary) % 8 != 0:
            # print(f"Warning: Binary string length ({len(clean_binary)}) is not multiple of 8")
            # Pad with zeros if needed
            last_byte_offset = (len(clean_binary) % 8)
            clean_binary = clean_binary + '0' * (8 - (len(clean_binary) % 8))
        else:
            last_byte_offset = 0

        # Convert to string, binary string
        # result = ''.join(hex(int(clean_binary[i:i+8], 2)) for i in range(0, len(clean_binary), 8)[2:])
        result = "".join(f"{(int(clean_binary[i:i+8], 2)):02x}" for i in range(0, len(clean_binary), 8))
        # print("Clean binary: ", clean_binary)
        # print("Converted string (hex): ", result, ", Write complete!")

                                                  
        return result, len_binary
    except ValueError as e:
        print(f"Error: Invalid binary string - {e}")
        return None
    except UnicodeDecodeError as e:
        print(f"Error: Cannot decode to UTF-8 - {e}")
        return None



class AdvancedMicroBlazeComm:
    def __init__(self, port='COM3', baudrate=9600):
        self.port = port
        self.baudrate = baudrate
        self.ser = None
        self.running = False
        self.receive_callback = None
        self.log_file = f"uart_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    
    def connect(self):
        """Connect to MicroBlaze with error handling"""
        try:
            self.ser = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=None  # Short timeout for non-blocking reads
            )
            
            # Clear buffers
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()
            
            print(f"✅ Connected to {self.port} at {self.baudrate} baud")
            time.sleep(2)  # Wait for MicroBlaze to initialize
            return True
            
        except serial.SerialException as e:
            print(f"❌ Connection failed: {e}")
            return False
    
    def start_receiving(self, callback=None):
        """Start background thread for receiving data"""
        self.receive_callback = callback
        self.running = True
        self.receive_thread = threading.Thread(target=self._receive_loop)
        self.receive_thread.daemon = True
        self.receive_thread.start()
        print("📡 Started receiving thread")
    
    def _receive_loop(self):
        """Background thread for receiving data"""
        read_index = 0
        while self.running and self.ser and self.ser.is_open:
            try:
                if self.ser.inWaiting() > 4096:
                    # Read all available data
                    data = self.ser.read_until(expected="\n\r\n\r")
                    print(data)
                    read_index = read_index + 1
                    print(read_index)
                    # Log received data
                    timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                    log_entry = f"[{timestamp}] RX: {repr(data)}"
                    print(log_entry)
                    
                    # Write to log file
                    with open(self.log_file, 'a', encoding='utf-8') as f:
                        f.write(log_entry + '\n')
                    
                    # Call callback if provided
                    if self.receive_callback:
                        self.receive_callback(data)
                    
                    time.sleep(0.01)  # Small delay to prevent CPU overload
                
            except Exception as e:
                print(f"Error in receive loop: {e}")
                break

    def receive_until(self):
        """Background thread for receiving data"""
        read_index = 0
        while self.running and self.ser and self.ser.is_open:
            try:
                # if self.ser.in_waiting > 0:
                    # Read all available databyte
                
                data = self.ser.read_until(expected="\n\r\n\r", size=4)
                print(data)
                read_index = read_index + 1
                print(read_index)
                # Log received data
                timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                log_entry = f"[{timestamp}] RX: {repr(data)}"
                print(log_entry)
                
                # Write to log file
                with open(self.log_file, 'a', encoding='utf-8') as f:
                    f.write(log_entry + '\n')
                
                # Call callback if provided
                if self.receive_callback:
                    self.receive_callback(data)
                
                time.sleep(0.01)  # Small delay to prevent CPU overload
                
            except Exception as e:
                print(f"Error in receive loop: {e}")
                break
        return data
        
    
    def send_data(self, data):
        """Send data to MicroBlaze"""
        if not self.ser or not self.ser.is_open:
            print("❌ Not connected")
            return False
        
        try:
            if isinstance(data, str):
                # data = data.encode('utf-8')
                # print("Sending string data: ", repr(data))
                data_sent = bytearray.fromhex(data)
            
            self.ser.write(data_sent)
            print("Hex string sent: ", data_sent.hex(), ", Write complete!")
            # print('\r'.encode('utf-8').hex())
            # self.ser.write('\r\r'.encode('utf-8'))  # send newline to indicate end of transmission
            # self.ser.write('\r'.encode('utf-8'))  # send newline to indicate end of transmission
            # self.ser.write('\r'.encode('utf-8'))  # send newline to indicate end of transmission
            # self.ser.write('\r'.encode('utf-8'))  # send newline to indicate end of transmission
            
            # Log sent data
            timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
            # log_entry = f"[{timestamp}] TX: {repr(data.decode('utf-8', errors='ignore'))}"
            # print(log_entry)
            
            return True
            
        except Exception as e:
            print(f"❌ Send failed: {e}")
            traceback.print_exc()
            return False
    
    def send_binary_data(self, data_bytes):
        """Send binary data to MicroBlaze"""
        if not self.ser or not self.ser.is_open:
            return False
        
        try:
            self.ser.write(data_bytes)
            print(f"📨 Sent binary data: {len(data_bytes)} bytes")
            return True
        except Exception as e:
            print(f"❌ Binary send failed: {e}")
            return False
        
    # read until sequence
    def read_until_sequence(self, terminator="\n\r\n\r", timeout=10, format="hex"):
        """
        Read from serial until the specific termination sequence is found
        """
        buffer = ""
        start_time = time.time()
        term_pattern_hex = terminator.encode('utf-8').hex()
        if format == "hex":
            terminator = term_pattern_hex
        while time.time() - start_time < timeout:
            if self.ser.inWaiting() > 0:
                # Read available data
                if format == "hex":
                    chunk = self.ser.read(self.ser.inWaiting())
                    buffer += chunk.hex()
                elif format == "str":
                    chunk = self.ser.read(self.ser.inWaiting()).decode('utf-8', errors='ignore')
                    buffer += chunk
                
                # print(f"↳ Received: {repr(chunk)}")  # Debug output
                
                # Check if termination sequence is in buffer
                if terminator in buffer:
                    # Split at the termination sequence and return data before it
                    if format == "hex":
                        term_index = buffer.find(terminator)
                        received_data = buffer[:term_index]
                        remaining_data = buffer[term_index + len(terminator):]  # Data after (if any)
                    elif format == "str":
                        data_parts = buffer.split(terminator)
                        received_data = data_parts[0]  # Data before terminator
                        remaining_data = terminator.join(data_parts[1:])  # Data after (if any) # Data after (if any)
                    # print(f"↳ Received: {(buffer)}")  # Debug output

                    # print(f"✅ Termination sequence found! Total received: {len(buffer)} chars")
                    return received_data, remaining_data
                    
            time.sleep(0.01)  # Small delay to prevent CPU overload
        print(f"⏰ Timeout - termination sequence not found")
        return buffer, ""
    
    def disconnect(self):
        """Clean disconnect"""
        self.running = False
        # if self.receive_thread.is_alive():
        #     self.receive_thread.join(timeout=1.0)
        
        if self.ser and self.ser.is_open:
            self.ser.close()
        print("🔌 Disconnected")

def hex_string_to_binary_string(hex_string):
    binary_string = ''.join(format(int(c, 16), '04b') for c in hex_string)
    return binary_string
    

# Callback function for received data
def on_data_received(data):
    """Custom callback for processing received data"""
    print(f"🔔 Callback received: {data}")

# add the function that checks "ready\n\r\n\r" from microblaze before sending data
def wait_for_microblaze_ready(obj):
    mb_ready_str = "".encode('utf-8').hex()
    while ("ready".encode('utf-8').hex() not in mb_ready_str):
        read_data, remaining = obj.read_until_sequence(terminator="\n\r\n\r", timeout=1000000, format="hex")
        mb_ready_str += read_data
        # print(mb_ready_str)
    # print("\n\n\n")
    print("The received string is: " + mb_ready_str)
    # print("\n\n\n")
    print("The received string in utf-8 is: " + (bytes.fromhex(mb_ready_str[0:]).decode('utf-8', errors='replace')))
    # print("\n\n\n")
    print("MicroBlaze is ready...")
    return mb_ready_str
    

    # print("MicroBlaze is ready.")

def toggle_latch(obj, scan_byp, current_scan_chain_data, last_byte_offset): # wrong behaviro here, come back to change it lateronce we defined the successful send signal
    try:
        # wait for the 
        # wait_for_microblaze_ready(obj)
        # 1 set enable for the first time
        control_byte = form_control_byte(scan_enable=0, scan_bypass=scan_byp, num_of_bits=last_byte_offset)
        control_byte_ascii = ''.join(chr(int(control_byte, 2)))
        control_byte_hex, _ = binary_to_string_safe(control_byte)
        # print("Current scan chain data : ", current_scan_chain_data)
        # print("The control byte is: ", control_byte)
        # print("The control byte (ASCII) is: ", control_byte_ascii)

        sent_string = control_byte_hex + current_scan_chain_data
        # print("Sent string: ", repr(sent_string))
        obj.send_data(sent_string)
        
        # 2 set enable to 0 for latch to be transparent
        wait_for_microblaze_ready(obj)

        control_byte = form_control_byte(scan_enable=1, scan_bypass=scan_byp, num_of_bits=last_byte_offset)
        control_byte_ascii = ''.join(chr(int(control_byte, 2)))
        control_byte_hex, _ = binary_to_string_safe(control_byte)

        # print("The control byte is: ", control_byte)
        # print("The control byte (ASCII) is: ", control_byte_ascii)
        sent_string = control_byte_hex + current_scan_chain_data
        obj.send_data(sent_string)

        # 3 set enable to 1 for latch to hold the data
        wait_for_microblaze_ready(obj)
        control_byte = form_control_byte(scan_enable=0, scan_bypass=scan_byp, num_of_bits=last_byte_offset)
        control_byte_ascii = ''.join(chr(int(control_byte, 2)))
        control_byte_hex, _ = binary_to_string_safe(control_byte)

        # print("The control byte is: ", control_byte)
        # print("The control byte (ASCII) is: ", control_byte_ascii)
        sent_string = control_byte_hex + current_scan_chain_data
        obj.send_data(sent_string)

        wait_for_microblaze_ready(obj)
        
        # print("Latch toggled successfully.")
        return sent_string
    except Exception as e:
        print(f"Error in toggle_latch: {e}")
        traceback.print_exc()
    
def write_scan_chain(obj, scan_byp, current_scan_chain_data, last_byte_offset):
    try:
        # wait for the 
        wait_for_microblaze_ready(obj)
        # send the data
        control_byte = form_control_byte(scan_enable=1, scan_bypass=scan_byp, num_of_bits=last_byte_offset)
        sent_string = control_byte + current_scan_chain_data
        obj.send_data(sent_string)
        print("Scan chain data sent successfully.")
        return sent_string
    except Exception as e:
        print(f"Error in write_scan_chain: {e}")
        traceback.print_exc()


# might need a dedicated bypass writer function both in python and microblaze controller

def mscan_en_bypass_writer(obj, scan_enable, scan_bypass):
    control_byte = form_control_byte(scan_enable=scan_enable, scan_bypass=scan_bypass, num_of_bits=0)
    control_byte_hex, num = binary_to_string_safe(control_byte)
    sent_string = control_byte_hex 
    obj.send_data(sent_string)
    wait_for_microblaze_ready(obj)


# For initial writing into the chip
# 1) write into the mscan chain with bypass=1 and en=0
# 2) After write finished, toggle 
def mscan_write(obj, mscan_sel, glb_control_bits="001", config_control_bits="001", fcw_control_bits="001", readout_control_bits="0", vcal_control_bits="001", scan_load_1bit="0"): # add selection of sub chain bits later
    
    if (mscan_sel != "bypass"):
        scan_bypass = 0
        scan_enable = 0
        print("scan_bypass set to 0 for sub chain writing.")
        print("scan_enable set to 0 for sub chain writing.")
        mscan_en_bypass_writer(obj, scan_enable=scan_enable, scan_bypass=scan_bypass)
    else:
        scan_bypass = 1
        scan_enable = 0
        print("scan_bypass set to 1 for sub chain writing.")
        print("scan_enable set to 0 for sub chain writing.")
        mscan_en_bypass_writer(obj, scan_enable=scan_enable, scan_bypass=scan_bypass)

    # if only write to mscan(bypass is on) 
        
    # concat the sub chain control bits
    # glb -> config -> fcw -> readout -> vcal -> scan_load
    # test_bin_str = "0101" * 20
    test_bin_str = ""
    sub_chain_control_bits = glb_control_bits + config_control_bits + fcw_control_bits + readout_control_bits + vcal_control_bits + scan_load_1bit
    print("Sub chain control bits are: ", (sub_chain_control_bits))
    # update the sub chain data bits from global variables
    sub_chain_data_bits = select_subchain(mscan_sel)[::-1]
    print("Selected sub chain data bits are: ", (sub_chain_data_bits))
    print("len of sub chain data bits: ", len(sub_chain_data_bits))

    mscan_complete = select_mscan_header(mscan_sel) + sub_chain_control_bits + test_bin_str
    print("mscan_complete length: ", len(mscan_complete))
    # sub_chain_data_bits
    if (mscan_sel == "bypass"):
        mscan_complete_ascii, last_byte_offset = binary_to_string_safe(mscan_complete[::-1])
    else:
        mscan_complete_ascii, last_byte_offset = binary_to_string_safe(mscan_complete[::-1] + sub_chain_data_bits)
    
    print("mscan_complete_binary is:" + repr(mscan_complete))
    print("mscan_complete_binary_inv is:" + repr(mscan_complete[::-1]))
    print("mscan_complete_ascii is:" + repr(mscan_complete_ascii))
    # not changing during the process of this master scan write
    
    # first write into the mscan chain with bypass=1 and en=0
    # scan_enable = 0 means the output latch is latching
    # bypass = 1 means only the mscan chain is active
    control_byte = form_control_byte(scan_enable=scan_enable, scan_bypass=scan_bypass, num_of_bits=last_byte_offset)
    control_byte_hex, num = binary_to_string_safe(control_byte)

    
    sent_string = control_byte_hex + mscan_complete_ascii
    print("mscan sent_string is:" + repr(sent_string))
    print("mscan_complete_ascii is:" + repr(mscan_complete_ascii))
    obj.send_data(sent_string)

    # mscan_en_bypass_writer(obj, scan_enable=0, scan_bypass=scan_bypass)
    # mscan_en_bypass_writer(obj, scan_enable=1, scan_bypass=scan_bypass)
    # mscan_en_bypass_writer(obj, scan_enable=0, scan_bypass=scan_bypass)

    wait_for_microblaze_ready(obj)

    control_byte = form_control_byte(scan_enable=scan_enable, scan_bypass=scan_bypass, num_of_bits=last_byte_offset)
    control_byte_hex, num = binary_to_string_safe(control_byte)

    
    sent_string = control_byte_hex + mscan_complete_ascii
    print("mscan sent_string is:" + repr(sent_string))
    print("mscan_complete_ascii is:" + repr(mscan_complete_ascii))
    obj.send_data(sent_string)

    wait_for_microblaze_ready(obj)

    control_byte = form_control_byte(scan_enable=scan_enable, scan_bypass=scan_bypass, num_of_bits=last_byte_offset)
    control_byte_hex, num = binary_to_string_safe(control_byte)

    
    sent_string = control_byte_hex + mscan_complete_ascii
    print("mscan sent_string is:" + repr(sent_string))
    print("mscan_complete_ascii is:" + repr(mscan_complete_ascii))
    obj.send_data(sent_string)

    wait_for_microblaze_ready(obj)


def toggle_en_mscan(obj):
    # when toggling enable of the latch, always make sure that bypass is high
    # you don't want the existing value of the sub chains to be altered
    # make sure the sub chain clocks are bypassed
    mscan_en_bypass_writer(obj, scan_enable=0, scan_bypass=1)
    mscan_en_bypass_writer(obj, scan_enable=1, scan_bypass=1)
    mscan_en_bypass_writer(obj, scan_enable=1, scan_bypass=1)
    mscan_en_bypass_writer(obj, scan_enable=1, scan_bypass=1)
    mscan_en_bypass_writer(obj, scan_enable=0, scan_bypass=1)

def toggle_sub_chain_en(obj, mscan_sel, glb_control_bits="001", config_control_bits="001", fcw_control_bits="001", readout_control_bits="0", vcal_control_bits="001", scan_load_1bit="0"):
    # toggle the enable of the sub chain
    if mscan_sel == "bypass":
        print("Bypass selected, no sub chain to toggle.")
        return
    elif mscan_sel == "glb":
        mscan_sel_bits = "10000"
        glb_control_en_zero = '0' + glb_control_bits[1:]
        glb_control_en_one = '1' + glb_control_bits[1:]
        sub_chain_control_bits_enz = glb_control_en_zero + config_control_bits + fcw_control_bits + readout_control_bits + vcal_control_bits + scan_load_1bit
        sub_chain_control_bits_eno = glb_control_en_one + config_control_bits + fcw_control_bits + readout_control_bits + vcal_control_bits + scan_load_1bit
    elif mscan_sel == "config":
        mscan_sel_bits = "00001"
        config_control_en_zero = '0' + config_control_bits[1:]
        config_control_en_one = '1' + config_control_bits[1:]
        sub_chain_control_bits_enz = glb_control_bits + config_control_en_zero + fcw_control_bits + readout_control_bits + vcal_control_bits + scan_load_1bit
        sub_chain_control_bits_eno = glb_control_bits + config_control_en_one + fcw_control_bits + readout_control_bits + vcal_control_bits + scan_load_1bit
    elif mscan_sel == "fcw":
        mscan_sel_bits = "00010"
        fcw_control_en_zero = '0' + fcw_control_bits[1:]
        print("fcw_control_en_zero is: " + fcw_control_en_zero)
        fcw_control_en_one = '1' + fcw_control_bits[1:]
        print("fcw_control_en_one is: " + fcw_control_en_one)
        sub_chain_control_bits_enz = glb_control_bits + config_control_bits + fcw_control_en_zero + readout_control_bits + vcal_control_bits + scan_load_1bit
        sub_chain_control_bits_eno = glb_control_bits + config_control_bits + fcw_control_en_one + readout_control_bits + vcal_control_bits + scan_load_1bit
    elif mscan_sel == "readout":
        mscan_sel_bits = "00100" 
        sub_chain_control_bits = glb_control_bits + config_control_bits + fcw_control_bits + readout_control_bits + vcal_control_bits + scan_load_1bit
    elif mscan_sel == "vcal":
        mscan_sel_bits = "01000"
        vcal_control_en_zero = '0' + vcal_control_bits[1:]
        vcal_control_en_one = '1' + vcal_control_bits[1:]
        sub_chain_control_bits_enz = glb_control_bits + config_control_bits + fcw_control_bits + readout_control_bits + vcal_control_en_zero + scan_load_1bit
        sub_chain_control_bits_eno = glb_control_bits + config_control_bits + fcw_control_bits + readout_control_bits + vcal_control_en_one + scan_load_1bit
    else:
        mscan_sel_bits = "00000"

    print("HOST: Toggling the enable of the " + mscan_sel + " sub scan chain...")
    
    sent_string = form_sent_string(scan_enable=0, scan_bypass=1, mscan_header=mscan_sel_bits, sub_chain_control_bits=sub_chain_control_bits_enz, sub_scan_data_bits="")
        
    obj.send_data(sent_string)
    wait_for_microblaze_ready(obj)
    # toggle mscan enable
    mscan_en_bypass_writer(obj, scan_enable=0, scan_bypass=1)
    mscan_en_bypass_writer(obj, scan_enable=1, scan_bypass=1)
    mscan_en_bypass_writer(obj, scan_enable=0, scan_bypass=1)

    # write back with enable = 1
    sent_string = form_sent_string(scan_enable=0, scan_bypass=1, mscan_header=mscan_sel_bits, sub_chain_control_bits=sub_chain_control_bits_eno, sub_scan_data_bits="")

    obj.send_data(sent_string)
    wait_for_microblaze_ready(obj)  

    # toggle mscan enable
    mscan_en_bypass_writer(obj, scan_enable=0, scan_bypass=1)
    mscan_en_bypass_writer(obj, scan_enable=1, scan_bypass=1)
    mscan_en_bypass_writer(obj, scan_enable=0, scan_bypass=1)

    # write back with enable = 1
    sent_string = form_sent_string(scan_enable=0, scan_bypass=1, mscan_header=mscan_sel_bits, sub_chain_control_bits=sub_chain_control_bits_enz, sub_scan_data_bits="")

    obj.send_data(sent_string)
    wait_for_microblaze_ready(obj)  

    # # toggle mscan enable
    mscan_en_bypass_writer(obj, scan_enable=0, scan_bypass=1)
    mscan_en_bypass_writer(obj, scan_enable=1, scan_bypass=1)
    mscan_en_bypass_writer(obj, scan_enable=0, scan_bypass=1)




# this function only write the master scan chain with desired control bits of 
def mscan_writer_only(obj, mscan_sel, glb_control_bits="001", config_control_bits="001", fcw_control_bits="001", readout_control_bits="0", vcal_control_bits="001", scan_load_1bit="0", mode=None, data_bits=None): # add selection of sub chain bits later

    if (mscan_sel == "bypass"):
        mscan_sel_bits = "00000"
    elif (mscan_sel == "glb"):
        mscan_sel_bits = "10000"
    elif (mscan_sel == "config"):
        mscan_sel_bits = "00001"
    elif (mscan_sel == "fcw"):
        mscan_sel_bits = "00010"
    elif (mscan_sel == "readout"):
        mscan_sel_bits = "00100"
    elif (mscan_sel == "vcal"):
        mscan_sel_bits = "01000"
    else:
        mscan_sel_bits = "00000"

    print("HOST: Make bypass high, only write to mscan chain...")
    mscan_en_bypass_writer(obj, scan_enable=0, scan_bypass=1)
    # write the mscan sel bits into the mscan chain with bypass=1
    # bypass = 1 ground the clock signal to sub scan chains
    sub_chain_control_bits = glb_control_bits + config_control_bits + fcw_control_bits + readout_control_bits + vcal_control_bits + scan_load_1bit

    # test, delete later
    mscan_complete = mscan_sel_bits + sub_chain_control_bits
    print("mscan_complete length: ", len(mscan_complete))
    mscan_complete_ascii, last_byte_offset = binary_to_string_safe(mscan_complete[::-1])
    # print("mscan_complete_binary is:" + repr(mscan_complete))   

    # make sure bypass is high when writing only to mscan chain
    mscan_en_bypass_writer(obj, scan_enable=0, scan_bypass=1)

    # generate control byte with bypass=1 and en=0 since we are only writing the scan chain
    control_byte = form_control_byte(scan_enable=0, scan_bypass=1, num_of_bits=last_byte_offset)
    control_byte_hex, num = binary_to_string_safe(control_byte)

    sent_string = control_byte_hex + mscan_complete_ascii
    obj.send_data(sent_string)
    wait_for_microblaze_ready(obj)

    # # test, delete later
    # print("HOST: The mscan chain written with mscan sel bits: " + mscan_sel_bits + ", now toggling the latch enable...")
    toggle_en_mscan(obj)
    print("HOST: MSCAN Latch toggled. Setting bypass to 0 and writing to sub scan chain...")
    # sub_chain_data_bits = select_subchain(mscan_sel)[::-1]
    # sub_chain_data_bits = select_subchain(mscan_sel, mode=mode)
    sub_chain_data_bits = data_bits

    # set bypass = 0
    mscan_en_bypass_writer(obj, scan_enable=0, scan_bypass=0)
    print("HOST: Bypass set to 0.")
    print("HOST: Writing to mscan chain + sub scan chain with bypass=0... With debug header bits")
    # prepare the sent string
    sent_string = form_sent_string(scan_enable=0, scan_bypass=0, mscan_header=mscan_sel_bits, sub_chain_control_bits=sub_chain_control_bits, sub_scan_data_bits=sub_chain_data_bits)

    # sent_string = control_byte_hex + mscan_complete_ascii
    print("mscan sent_string is:" + repr(sent_string))
    # send
    obj.send_data(sent_string)
    # read
    readback_string = wait_for_microblaze_ready(obj)
    
    # process 
    ext_bin_readback = extract_bin_from_hex_string(readback_string)
    print("HOST: the 1st full readback signal is: " + ext_bin_readback)
    # print("Readback string is (1): " + (readback_string))
    # test, write twice to see the read back value

    print("third write to the msacn chain + " + mscan_sel)
    # prepare the sent string
    sent_string = form_sent_string(scan_enable=0, scan_bypass=0, mscan_header=mscan_sel_bits, 
    sub_chain_control_bits=sub_chain_control_bits, sub_scan_data_bits=sub_chain_data_bits)

    # send
    obj.send_data(sent_string)
    # read
    readback_string = wait_for_microblaze_ready(obj)
    # process 
    ext_bin_readback = extract_bin_from_hex_string(readback_string)
    # print("the sent     string is: " + sent_string[2:])
    print("HOST: the 2nd full readback signal is: " + ext_bin_readback)

    # set bypass back to 1
    print("HOST: Setting bypass back to 1...")
    mscan_en_bypass_writer(obj, scan_enable=0, scan_bypass=1)
    print("HOST: Bypass set to 1.")

    toggle_sub_chain_en(obj, mscan_sel, glb_control_bits, config_control_bits, fcw_control_bits, readout_control_bits, vcal_control_bits, scan_load_1bit)


def toggle_scan_load(obj, mscan_sel, glb_control_bits="001", config_control_bits="001", fcw_control_bits="001", readout_control_bits="0", vcal_control_bits="001", scan_load_1bit="0"):
    if (mscan_sel == "bypass"):
        mscan_sel_bits = "00000"
    elif (mscan_sel == "glb"):
        mscan_sel_bits = "10000"
    elif (mscan_sel == "config"):
        mscan_sel_bits = "00001"
    elif (mscan_sel == "fcw"):
        mscan_sel_bits = "00010"
    elif (mscan_sel == "readout"):
        mscan_sel_bits = "00100"
    elif (mscan_sel == "vcal"):
        mscan_sel_bits = "01000"
    else:
        mscan_sel_bits = "00000"

    print("HOST: Toggling the scan load bit of the mscan chain...")
    mscan_en_bypass_writer(obj, scan_enable=0, scan_bypass=1)
    # write the mscan sel bits into the mscan chain with bypass=1
    # bypass = 1 ground the clock signal to sub scan chains
    sub_chain_control_bits_loadzero = glb_control_bits + config_control_bits + fcw_control_bits + readout_control_bits + vcal_control_bits + '0'

    sub_chain_control_bits_loadone = glb_control_bits + config_control_bits + fcw_control_bits + readout_control_bits + vcal_control_bits + '1'

    mscan_complete_loadzero = mscan_sel_bits + sub_chain_control_bits_loadzero
    mscan_complete_ascii_loadzero, last_byte_offset = binary_to_string_safe(mscan_complete_loadzero[::-1])

    control_byte = form_control_byte(scan_enable=0, scan_bypass=1, num_of_bits=last_byte_offset)

    control_byte_hex, num = binary_to_string_safe(control_byte)

    sent_string = control_byte_hex + mscan_complete_ascii_loadzero
    obj.send_data(sent_string)  
    wait_for_microblaze_ready(obj)

    print("HOST: Scan load bit set to 0, now toggling to 1...")


    mscan_complete_loadone = mscan_sel_bits + sub_chain_control_bits_loadone
    mscan_complete_ascii_loadone, last_byte_offset = binary_to_string_safe(mscan_complete_loadone[::-1])

    control_byte = form_control_byte(scan_enable=0, scan_bypass=1, num_of_bits=last_byte_offset)
    control_byte_hex, num = binary_to_string_safe(control_byte)
    sent_string = control_byte_hex + mscan_complete_ascii_loadone
    obj.send_data(sent_string)
    wait_for_microblaze_ready(obj)

    print("HOST: Scan load bit toggled back to 0...")
    mscan_complete_loadzero = mscan_sel_bits + sub_chain_control_bits_loadzero
    mscan_complete_ascii_loadzero, last_byte_offset = binary_to_string_safe(mscan_complete_loadzero[::-1])

    control_byte = form_control_byte(scan_enable=0, scan_bypass=1, num_of_bits=last_byte_offset)

    control_byte_hex, num = binary_to_string_safe(control_byte)

    sent_string = control_byte_hex + mscan_complete_ascii_loadzero
    obj.send_data(sent_string)  
    wait_for_microblaze_ready(obj)

def decode_readout_bits(hex_string):
    bin_str = hex_to_binary(hex_string)

    bin_str_len = len(bin_str)
    print("Length of the decoded binary string: " + str(bin_str_len))

    bin_str_inv = bin_str[::-1]
    full_eavg = 268435456
    mscan_control = bin_str_inv[1:20]
    print("Decoded MSCAN control bits: " + mscan_control)
    print("Length of MSCAN control bits: " + str(len(mscan_control)))
    chip_id = bin_str_inv[20:30] 
    print("Decoded Chip ID bits: " + chip_id)
    print("Length of Chip ID bits: " + str(len(chip_id)))
    full_fcw = bin_str_inv[30:82]
    print("Decoded Full FCW bits: " + full_fcw)
    print("Length of Full FCW bits: " + str(len(full_fcw)))
    eavg_normal = bin_str_inv[82:110]
    print("Decoded EAVG Normal bits: " + eavg_normal)
    print("Length of EAVG Normal bits: " + str(len(eavg_normal)))
    print("percentage value of EAVG Normal: " + str(int(eavg_normal, 2) / full_eavg * 100) + "%")
    eavg_perturb = bin_str_inv[110:138]
    print("Decoded EAVG Perturb bits: " + eavg_perturb)
    print("Length of EAVG Perturb bits: " + str(len(eavg_perturb)))
    print("percentage value of EAVG Perturb: " + str(int(eavg_perturb, 2) / full_eavg * 100) + "%")
    int_upd0 = bin_str_inv[138:190]
    print("Decoded INT UPD0 bits: " + int_upd0)
    print("Length of INT UPD0 bits: " + str(len(int_upd0)))
    prop_upd0 = bin_str_inv[190:242]
    print("Decoded PROP UPD0 bits: " + prop_upd0)   
    print("Length of PROP UPD0 bits: " + str(len(prop_upd0)))
    gm_log_int_ff = bin_str_inv[242:249]
    print("Decoded GM LOG INT FF bits: " + gm_log_int_ff)
    print("Length of GM LOG INT FF bits: " + str(len(gm_log_int_ff)))
    rs_ff = bin_str_inv[249:257]
    print("Decoded RS FF bits: " + rs_ff)
    print("Length of RS FF bits: " + str(len(rs_ff)))
    scan_out_zt = bin_str_inv[257:263]
    print("Decoded SCAN OUT ZT bits: " + scan_out_zt)
    print("Length of SCAN OUT ZT bits: " + str(len(scan_out_zt)))






def readout_scan_read(obj, mscan_sel, glb_control_bits="001", config_control_bits="001", fcw_control_bits="001", readout_control_bits="0", vcal_control_bits="001", scan_load_1bit="0"):

    if (mscan_sel == "bypass"):
        mscan_sel_bits = "00000"
    elif (mscan_sel == "glb"):
        mscan_sel_bits = "10000"
    elif (mscan_sel == "config"):
        mscan_sel_bits = "00001"
    elif (mscan_sel == "fcw"):
        mscan_sel_bits = "00010"
    elif (mscan_sel == "readout"):
        mscan_sel_bits = "00100"
    elif (mscan_sel == "vcal"):
        mscan_sel_bits = "01000"
    else:
        mscan_sel_bits = "00000"

    print("HOST: Performing readout scan read...")
    # set the bypass signal to be high first
    mscan_en_bypass_writer(obj, scan_enable=0, scan_bypass=1)

    sub_chain_control_bits_scanloadzero = glb_control_bits + config_control_bits + fcw_control_bits + '0' + vcal_control_bits + '0'

    sub_chain_control_bits_scanloadone = glb_control_bits + config_control_bits + fcw_control_bits + '0' + vcal_control_bits + '1'

    mscan_complete_scanloadzero = mscan_sel_bits + sub_chain_control_bits_scanloadzero
    mscan_complete_ascii_scanloadzero, last_byte_offset = binary_to_string_safe(mscan_complete_scanloadzero[::-1])

    control_byte = form_control_byte(scan_enable=0, scan_bypass=1, num_of_bits=last_byte_offset)    
    control_byte_hex, num = binary_to_string_safe(control_byte)

    sent_string = control_byte_hex + mscan_complete_ascii_scanloadzero
    obj.send_data(sent_string)  
    wait_for_microblaze_ready(obj)

    toggle_en_mscan(obj)


    print("HOST: Scan load bit set to 0, now performing readout...")

    mscan_complete_scanloadone = mscan_sel_bits + sub_chain_control_bits_scanloadone
    mscan_complete_ascii_scanloadone, last_byte_offset = binary_to_string_safe(mscan_complete_scanloadone[::-1])

    control_byte = form_control_byte(scan_enable=0, scan_bypass=1, num_of_bits=last_byte_offset)    
    control_byte_hex, num = binary_to_string_safe(control_byte)

    sent_string = control_byte_hex + mscan_complete_ascii_scanloadone
    obj.send_data(sent_string)  
    wait_for_microblaze_ready(obj)

    toggle_en_mscan(obj)

    mscan_en_bypass_writer(obj, scan_enable=0, scan_bypass=0)
    print("HOST: Readout scan read performed, scan load bit set back to 0...")
    sub_chain_control_bits_scanloadzero = glb_control_bits + config_control_bits + fcw_control_bits + '1' + vcal_control_bits + '0'
    mscan_complete_scanloadzero = mscan_sel_bits + sub_chain_control_bits_scanloadzero
    mscan_complete_ascii_scanloadzero, last_byte_offset = binary_to_string_safe(mscan_complete_scanloadzero[::-1])

    control_byte = form_control_byte(scan_enable=0, scan_bypass=0, num_of_bits=last_byte_offset)    
    control_byte_hex, num = binary_to_string_safe(control_byte)

    sent_string = control_byte_hex + mscan_complete_ascii_scanloadzero
    obj.send_data(sent_string)  
    wait_for_microblaze_ready(obj)

    toggle_en_mscan(obj)


    # readout the loaded data, scanread_complete
    

    sub_chain_data_bits = scanread_complete
    mscan_en_bypass_writer(obj, scan_enable=0, scan_bypass=0)
    
    sent_string = form_sent_string(scan_enable=0, scan_bypass=0, mscan_header=mscan_sel_bits, sub_chain_control_bits=sub_chain_control_bits_scanloadzero, sub_scan_data_bits=sub_chain_data_bits)
    obj.send_data(sent_string)
    # read
    readback_string = wait_for_microblaze_ready(obj)
    
    # process 
    ext_bin_readback = extract_bin_from_hex_string(readback_string)
    print("HOST: the 1st full readback signal is: " + ext_bin_readback)
    decode_readout_bits(ext_bin_readback)

    # write again to confirm
    sent_string = form_sent_string(scan_enable=0, scan_bypass=0, mscan_header=mscan_sel_bits, sub_chain_control_bits=sub_chain_control_bits_scanloadzero, sub_scan_data_bits=sub_chain_data_bits)
    obj.send_data(sent_string)
    # read
    readback_string = wait_for_microblaze_ready(obj)
    
    # process 
    ext_bin_readback = extract_bin_from_hex_string(readback_string)
    print("HOST: the 2nd full readback signal is: " + ext_bin_readback)
    decode_readout_bits(ext_bin_readback)
    mscan_en_bypass_writer(obj, scan_enable=0, scan_bypass=1)




# if chip_scan_chain_inv in "001101010011010100110101001101010101":
#     print("Found the chip scan chain in the control stream!")
# Usage example
# if __name__ == "__main__":

#     comm = AdvancedMicroBlazeComm(port='COM3', baudrate=9600)  # make port connection

#     if comm.connect(): # connect the uart 

        # mscan_writer_only(comm, mscan_sel="config", glb_control_bits="011", config_control_bits="011", fcw_control_bits="011", readout_control_bits="0", vcal_control_bits="000", scan_load_1bit="0", mode="reset")

        # mscan_writer_only(comm, mscan_sel="glb", glb_control_bits="011", config_control_bits="000", fcw_control_bits="011", readout_control_bits="0",  vcal_control_bits="000", scan_load_1bit="0", mode="bgpwrdn")

        # mscan_writer_only(comm, mscan_sel="glb", glb_control_bits="011", config_control_bits="000", fcw_control_bits="011", readout_control_bits="0", vcal_control_bits="000", scan_load_1bit="0", mode="normal")
    
        # mscan_writer_only(comm, mscan_sel="glb", glb_control_bits="011", config_control_bits="000", fcw_control_bits="011", readout_control_bits="0", vcal_control_bits="000", scan_load_1bit="0", mode="reset")

        # mscan_writer_only(comm, mscan_sel="glb", glb_control_bits="011", config_control_bits="011", fcw_control_bits="011", readout_control_bits="0", vcal_control_bits="000", scan_load_1bit="0", mode="normal")

        # mscan_writer_only(comm, mscan_sel="fcw", glb_control_bits="011", config_control_bits="011", fcw_control_bits="011", readout_control_bits="0", vcal_control_bits="000", scan_load_1bit="0")

        # mscan_en_bypass_writer(comm, scan_enable=0, scan_bypass=1)

        # mscan_writer_only(comm, mscan_sel="config", glb_control_bits="011", config_control_bits="011", fcw_control_bits="011", readout_control_bits="0", vcal_control_bits="000", scan_load_1bit="0")

        # mscan_en_bypass_writer(comm, scan_enable=0, scan_bypass=1)
        # mscan_en_bypass_writer(comm, scan_enable=1, scan_bypass=1)
        # mscan_en_bypass_writer(comm, scan_enable=0, scan_bypass=1)

        # mscan_writer_only(comm, mscan_sel="config", glb_control_bits="011", config_control_bits="011", fcw_control_bits="000", readout_control_bits="0", vcal_control_bits="000", scan_load_1bit="0")

        

        # mscan_writer_only(comm, mscan_sel="glb", glb_control_bits="011", config_control_bits="011", fcw_control_bits="000", readout_control_bits="0", vcal_control_bits="000", scan_load_1bit="0", mode="normal")
      
        # mscan_writer_only(comm, mscan_sel="config", glb_control_bits="011", config_control_bits="011", fcw_control_bits="000", readout_control_bits="0", vcal_control_bits="000", scan_load_1bit="0", mode="reset")

        # mscan_writer_only(comm, mscan_sel="fcw", glb_control_bits="011", config_control_bits="011", fcw_control_bits="011", readout_control_bits="0", vcal_control_bits="000", scan_load_1bit="0")
        
        # mscan_writer_only(comm, mscan_sel="fcw", glb_control_bits="011", config_control_bits="011", fcw_control_bits="011", readout_control_bits="0", vcal_control_bits="000", scan_load_1bit="0")
        
        # mscan_writer_only(comm, mscan_sel="glb", glb_control_bits="011", config_control_bits="011", fcw_control_bits="000", readout_control_bits="0", vcal_control_bits="000", scan_load_1bit="0", mode="normal")

        # mscan_writer_only(comm, mscan_sel="config", glb_control_bits="011", config_control_bits="011", fcw_control_bits="000", readout_control_bits="0", vcal_control_bits="000", scan_load_1bit="0")
        
        

        # # mscan_writer_only(comm, mscan_sel="config", glb_control_bits="011", config_control_bits="011", fcw_control_bits="000", readout_control_bits="0", vcal_control_bits="000", scan_load_1bit="0")

        # time.sleep(10)

        # readout_scan_read(comm, mscan_sel="readout", glb_control_bits="011", config_control_bits="011", fcw_control_bits="000", readout_control_bits="0", vcal_control_bits="000", scan_load_1bit="0")

        # # mscan_writer_only(comm, mscan_sel="fcw", glb_control_bits="011", config_control_bits="011", fcw_control_bits="001", readout_control_bits="0", vcal_control_bits="000", scan_load_1bit="0")
        


