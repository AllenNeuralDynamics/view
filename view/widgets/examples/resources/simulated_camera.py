import logging
import numpy
import time
from multiprocessing import Process
from threading import Thread

# constants for VP-151MX camera
BUFFER_SIZE_FRAMES = 8
MIN_WIDTH_PX = 64    
MAX_WIDTH_PX = 14192
DIVISIBLE_WIDTH_PX = 16
MIN_HEIGHT_PX = 2
MAX_HEIGHT_PX = 10640
DIVISIBLE_HEIGHT_PX = 1
MIN_EXPOSURE_TIME_MS = 0.001
MAX_EXPOSURE_TIME_MS = 6e4

PIXEL_TYPES = {
    "mono8":  "uint8",
    "mono16": "uint16"
}

LINE_INTERVALS_US = {
    "mono8":  15.00,
    "mono16": 45.44
}

class Camera:

    def __init__(self, id):

        self.log = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.id = id
        self.simulated_pixel_type = "mono8"
        self.simulated_line_interval_us = 10
        self.simulated_width_px = 2032
        self.simulated_height_px = 2032
        self.simulated_width_offset_px = 0
        self.simulated_height_offset_px = 0
        self.simulated_exposure_time_ms = 1000

    @property
    def exposure_time_ms(self):
        return self.simulated_exposure_time_ms

    @exposure_time_ms.setter
    def exposure_time_ms(self, exposure_time_ms: float):

        if exposure_time_ms < MIN_EXPOSURE_TIME_MS or \
           exposure_time_ms > MAX_EXPOSURE_TIME_MS:
            self.log.error(f"exposure time must be >{MIN_EXPOSURE_TIME_MS} ms \
                             and <{MAX_EXPOSURE_TIME_MS} ms")
            raise ValueError(f"exposure time must be >{MIN_EXPOSURE_TIME_MS} ms \
                             and <{MAX_EXPOSURE_TIME_MS} ms")

        # Note: round ms to nearest us
        self.simulated_exposure_time_ms = exposure_time_ms
        self.log.info(f"exposure time set to: {exposure_time_ms} ms")

    @property
    def roi(self):
        return {'width_px': self.simulated_width_px,
                'height_px': self.simulated_height_px,
                'width_offset_px': self.simulated_width_offset_px,
                'height_offest_px': self.simulated_height_offset_px}

    @roi.setter
    def roi(self, roi: dict):

        width_px = roi['width_px']
        height_px = roi['height_px']

        sensor_height_px = MAX_HEIGHT_PX
        sensor_width_px = MAX_WIDTH_PX

        if height_px < MIN_WIDTH_PX or \
           (height_px % DIVISIBLE_HEIGHT_PX) != 0 or \
           height_px > MAX_HEIGHT_PX:
            self.log.error(f"Height must be >{MIN_HEIGHT_PX} px, \
                             <{MAX_HEIGHT_PX} px, \
                             and a multiple of {DIVISIBLE_HEIGHT_PX} px!")
            raise ValueError(f"Height must be >{MIN_HEIGHT_PX} px, \
                             <{MAX_HEIGHT_PX} px, \
                             and a multiple of {DIVISIBLE_HEIGHT_PX} px!")

        if width_px < MIN_WIDTH_PX or \
           (width_px % DIVISIBLE_WIDTH_PX) != 0 or \
           width_px > MAX_WIDTH_PX:
            self.log.error(f"Width must be >{MIN_WIDTH_PX} px, \
                             <{MAX_WIDTH_PX}, \
                            and a multiple of {DIVISIBLE_WIDTH_PX} px!")
            raise ValueError(f"Width must be >{MIN_WIDTH_PX} px, \
                             <{MAX_WIDTH_PX}, \
                            and a multiple of {DIVISIBLE_WIDTH_PX} px!")

        # width offset must be a multiple of the divisible width in px
        centered_width_offset_px = round((sensor_width_px/2 - width_px/2)/DIVISIBLE_WIDTH_PX)*DIVISIBLE_WIDTH_PX  
        # Height offset must be a multiple of the divisible height in px
        centered_height_offset_px = round((sensor_height_px/2 - height_px/2)/DIVISIBLE_HEIGHT_PX)*DIVISIBLE_HEIGHT_PX

        self.simulated_width_px = width_px
        self.simulated_height_px = height_px
        self.simulated_width_offset_px = centered_width_offset_px
        self.simulated_height_offset_px = centered_height_offset_px
        self.log.info(f"roi set to: {width_px} x {height_px} [width x height]")
        self.log.info(f"roi offset set to: {centered_width_offset_px} x {centered_height_offset_px} [width x height]")

    @property
    def pixel_type(self):
        pixel_type = self.simulated_pixel_type
        # invert the dictionary and find the abstracted key to output
        #return next(key for key, value in PIXEL_TYPES.items() if value == pixel_type)
        return pixel_type

    @pixel_type.setter
    def pixel_type(self, pixel_type_bits: str):
        valid = list(PIXEL_TYPES.keys())
        if pixel_type_bits not in valid:
            raise ValueError("pixel_type_bits must be one of %r." % valid)
        self.simulated_pixel_type = pixel_type_bits
        # self.simulated_pixel_type = PIXEL_TYPES[pixel_type_bits]
        #self.simulated_line_interval_us = pixel_type_bits
        # self.log.info(f"pixel type set_to: {pixel_type_bits}")

    @property
    def line_interval_us(self):
        return self.simulated_line_interval_us

    @property
    def sensor_width_px(self):
        return MAX_WIDTH_PX

    @property
    def sensor_height_px(self):
        return MAX_HEIGHT_PX

    def prepare(self):
        self.log.info('simulated camera preparing...')
        self.buffer = list()

    def start(self, frame_count: int, live: bool = False):
        self.log.info('simulated camera starting...')
        self.thread = Thread(target=self.generate_frames, args=(frame_count,))
        self.thread.daemon = True
        self.thread.start()

    def stop(self):
        self.log.info('simulated camera stopping...')
        self.thread.join()

    def grab_frame(self):
        while not self.buffer:
            time.sleep(0.01)
        image = self.buffer.pop(0)
        return image

    def get_camera_acquisition_state(self):
        """return a dict with the state of the acquisition buffers"""
        # Detailed description of constants here:
        # https://documentation.euresys.com/Products/Coaxlink/Coaxlink/en-us/Content/IOdoc/egrabber-reference/
        # namespace_gen_t_l.html#a6b498d9a4c08dea2c44566722699706e
        state = {}
        state['frame_index'] = self.frame
        state['in_buffer_size'] = len(self.buffer)
        state['out_buffer_size'] = BUFFER_SIZE_FRAMES - len(self.buffer)
         # number of underrun, i.e. dropped frames
        state['dropped_frames'] = self.dropped_frames
        state['data_rate'] = self.frame_rate*self.simulated_width_px*self.simulated_height_px*numpy.dtype(self.simulated_pixel_type).itemsize/1e6
        state['frame_rate'] = self.frame_rate
        self.log.info(f"id: {self.id}, "
                      f"frame: {state['frame_index']}, "
                      f"input: {state['in_buffer_size']}, "
                      f"output: {state['out_buffer_size']}, "
                      f"dropped: {state['dropped_frames']}, "
                      f"data rate: {state['data_rate']:.2f} [MB/s], "
                      f"frame rate: {state['frame_rate']:.2f} [fps].")

    def generate_frames(self, frame_count: int):
        self.frame = 0
        self.dropped_frames = 0
        while self.frame < frame_count:
            start_time = time.time()
            column_count = self.simulated_width_px
            row_count = self.simulated_height_px
            frame_time_s = (row_count*self.simulated_line_interval_us/1000+self.simulated_exposure_time_ms)/1000
            # image = numpy.random.randint(low=128, high=256, size=(row_count, column_count), dtype=self.simulated_pixel_type)
            image = numpy.zeros(shape=(row_count, column_count), dtype=self.simulated_pixel_type)
            while (time.time() - start_time) < frame_time_s:
                time.sleep(0.01)
            if len(self.buffer) < BUFFER_SIZE_FRAMES:
                self.buffer.append(image)
            else:
                self.dropped_frames += 1
                self.log.warning('buffer full, frame dropped.')
            self.frame += 1
            end_time = time.time()
            self.frame_rate = 1/(end_time - start_time)
