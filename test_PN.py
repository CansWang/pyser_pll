from pyser import *

# this is the test script for general purpose Phase Noise Measurement Tests


started = False


# place to change division ratios before power on

    # main feedback divider setting 
    # 54 bits in total
    # the bottom 33 bits are the fractional part
    # the top 21 bits are the integer part    
CLKF_bits = reg_bits( '0' * 16 + '01111' + '0000000000' + '0' * 23, 54, 'bin')

    # Additional divider settings for the low speed output clocks
CLKOD_bits = reg_bits( '000' )

# update the GLB scan bits



# Power On
if not started:
    # power on script
    print("即将上电...")
    input("请检查1.8V IO电压是否设定到1.5V，确认后按回车继续")




CLKF_bits = reg_bits( '0' * 16 + '01111' + '0000000000' + '0' * 23, 54, 'bin') # 54 bits
print(update_glb_scan_string(CLKF_bits=CLKF_bits))
print("Length of updated glb scan string: ", len(update_glb_scan_string(CLKF_bits=CLKF_bits)))

