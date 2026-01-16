from pyser import *

# this is the test script for testing frequency jump settling time

# if powered up already, set started = True
# started = False
started = True

# place to change division ratios before power on

# reg_bits construction: reg_bits( value_string, total_bits, format )

    # main feedback divider setting 
    # 54 bits in total
    # the bottom 33 bits are the fractional part
    # the top 21 bits are the integer part 
    #                            integer   fractional part   
CLKF_bits = reg_bits( '0' * 16 + '01001' + '0000000000' + '0' * 23, 54, 'bin')
    # feedback division ratio  = CLKF
    # Additional divider settings for the low speed output clocks

CLKOD_bits = reg_bits( '7', 11, 'dec' )
    # low speed output divider
    # low speed output clock = Fref * CLKF / (CLKOD + 1)

    # high speed output frequency is adapted automatically inside the PLL

# update the GLB scan bits
glb_complete, glb_complete_reset, glb_complete_bgpwrdn = update_all_glb_scan_bits(CLKF_bits=CLKF_bits, CLKOD_bits=CLKOD_bits)


# change the variable in config scan chain if needed
config_byp_rs_en = reg_bits('1', 1, 'dec')  # bypass the right shift value, active high

# setting the bandwidth 
config_fi_log = reg_bits('2048', 16, 'dec') 
config_fd_log = reg_bits('128', 16, 'dec') 
config_rs_cnt_thres_dft =       reg_bits('127',   18,   'dec')  
config_rs_dec =                 reg_bits('1',   8,    'dec')
config_rs_inc =                 reg_bits('1',   8,    'dec')

config_lpfltr_dly = reg_bits('8', 8, 'dec')
config_fullbw_gm_lg =        reg_bits('36', 8, 'dec')
config_fullbw_gm_lg_offset = reg_bits('4', 8, 'dec')
rs_mask_en = reg_bits('0', 1, 'dec')
config_rs_val =      reg_bits('11',   8,   'dec')
config_rs_mask =     reg_bits('3',   8,   'dec')
rs_settling_plateau_en = reg_bits('0', 1, 'dec')
config_rs_sp_state_code =      reg_bits('16',   6,   'dec')

# update config scan chain
config_complete, config_complete_reset = update_all_config_scan_bits(config_byp_rs_en=config_byp_rs_en, config_fi_log=config_fi_log, config_fd_log=config_fd_log, config_rs_cnt_thres_dft=config_rs_cnt_thres_dft, config_rs_dec=config_rs_dec, config_rs_inc=config_rs_inc, config_lpfltr_dly=config_lpfltr_dly, config_fullbw_gm_lg=config_fullbw_gm_lg, config_fullbw_gm_lg_offset=config_fullbw_gm_lg_offset, rs_mask_en=rs_mask_en, config_rs_sp_state_code=config_rs_sp_state_code)

# print("Config Scan String        :", config_complete)
# print("Config Reset Scan String  :", config_complete_reset)
# print("Length of Config Scan String:", len(config_complete))
# print("Length of Config Reset Scan String:", len(config_complete_reset))

# print("GLB Scan String        :", glb_complete)
# print("GLB Reset Scan String  :", glb_complete_reset)
# print("GLB BGPWRDN Scan String:", glb_complete_bgpwrdn)
# print("Length of GLB Scan String:", len(glb_complete))
# print("Length of GLB Reset Scan String:", len(glb_complete_reset))
# print("Length of GLB BGPWRDN Scan String:", len(glb_complete_bgpwrdn))


# comm port connection

comm = AdvancedMicroBlazeComm(port='COM3', baudrate=9600)  # make port connection

if comm.connect(): # connect the uart 

    # Power On
    if not started:
        # power on script
        print("即将上电...")
        input("请检查1.8V IO电压是否设定到1.5V，确认后按回车继续")
        power_on(comm, config_complete, config_complete_reset, glb_complete, glb_complete_reset, glb_complete_bgpwrdn)
        print("上电完成")

    glb_writer_after_por(comm, glb_complete)
    control_reset_assert(comm, config_complete, config_complete_reset)
    print("释放控制环路复位...")
    # release the control loop reset

    # set the fcw
    # double check the fcw bits order, little endian or big endian?
                    #frac       # varactor  # cap bank   #4-7 div  # 2^n divider
    fcw = reg_bits( '0' * 23 + '00000000' + '00000' +    '00' +        '000',         41, 'bin', inv=False).binary_str  # 41 bits
    free_running_set_fcw(comm, fcw)

    # readout important parameter
    # readout(comm)
    free_running_readout_mode(comm)

    # disconnect the uart
    time.sleep(1)
    comm.disconnect()