"""Rev-B display GPIO assignment; GPIO numbers differ from QFN pad numbers."""
# RGB565 bit order for esp_lcd: B[0..4], G[0..5], R[0..4].
RGB_SIGNALS = ([f'LCD_B{i}' for i in range(3,8)] +
               [f'LCD_G{i}' for i in range(2,8)] +
               [f'LCD_R{i}' for i in range(3,8)])
TIMING_SIGNALS = ['LCD_PCLK','LCD_HSYNC','LCD_VSYNC','LCD_DE','LCD_DISP']
TOUCH_SIGNALS = ['TOUCH_SCL','TOUCH_SDA','TOUCH_INT','TOUCH_RST_N']
# Alternate top-row data pads are trapped behind bypass copper; use free right GPIOs.
GPIO_SIGNALS = dict(zip([39,40,41,42,43,44,45,46,47,32,49,26,51,28,53,30], RGB_SIGNALS))
GPIO_SIGNALS.update(dict(zip(range(9,14), TIMING_SIGNALS)))
GPIO_SIGNALS.update(dict(zip(range(15,19), TOUCH_SIGNALS)))
MCU_PORTS = [('MCU_'+n, 'bidirectional' if n in ('TOUCH_SCL','TOUCH_SDA','TOUCH_INT') else 'output')
             for n in RGB_SIGNALS+TIMING_SIGNALS+TOUCH_SIGNALS]
DISPLAY_PORTS = [('LCD_VDD','input'),('TOUCH_VDD','input'),('BL_LED_A','input'),
                 ('BL_LED_K','bidirectional'),('GND','bidirectional')]+[
                    (name,'bidirectional' if kind=='bidirectional' else 'input')
                    for name,kind in MCU_PORTS]
