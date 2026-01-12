from pyser import *

# this is the test script for testing frequency jump settling time

# if powered up already, set started = True
started = False

# place to change division ratios before power on

# reg_bits construction: reg_bits( value_string, total_bits, format )

    # main feedback divider setting 
    # 54 bits in total
    # the bottom 33 bits are the fractional part
    # the top 21 bits are the integer part 
    #                            integer   fractional part   
CLKF_bits = reg_bits( '0' * 16 + '01100' + '0000000000' + '0' * 23, 54, 'bin')
    # feedback division ratio  = CLKF
    # Additional divider settings for the low speed output clocks

CLKOD_bits = reg_bits( '0', 11, 'dec' )
    # low speed output divider
    # low speed output clock = Fref * CLKF / (CLKOD + 1)

    # high speed output frequency is adapted automatically inside the PLL

# update the GLB scan bits
glb_complete, glb_complete_reset, glb_complete_bgpwrdn = update_all_glb_scan_bits(CLKF_bits=CLKF_bits, CLKOD_bits=CLKOD_bits)


# change the variable in config scan chain if needed
config_byp_rs_en = reg_bits('0', 1, 'dec')  # bypass the right shift value, active high

# setting the bandwidth 
config_fi_log = reg_bits('2048', 16, 'dec') 
config_fd_log = reg_bits('2048', 16, 'dec') 


# update config scan chain
config_complete, config_complete_reset = update_all_config_scan_bits(config_byp_rs_en=config_byp_rs_en, config_fi_log=config_fi_log, config_fd_log=config_fd_log)

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
        
    control_reset_release(comm, config_complete, config_complete_reset)
    print("释放控制环路复位...")
    # release the control loop reset

    # readout important parameter
    # readout(comm)

    # disconnect the uart
    time.sleep(1)
    comm.disconnect()