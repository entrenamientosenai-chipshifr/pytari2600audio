from dataclasses import dataclass


@dataclass
class TIAChannelState:
    audio_ctrl: int = 0
    audio_freq: int = 0
    audio_vol: int = 0
    poly4_state: int = 0xF
    poly5_state: int = 0x1F
    freq_phase: int = 0


class TIA_Sound(object):
    def __init__(self, clocks):
        print("TiaSound chip created")

        # CPU Clock rate, used to scale to real time.
        # This tracks the TIA color clock, which is 3x the CPU clock.
        self.CPU_CLOCK_RATE = 3580000

        self.SAMPLERATE = 32050
        self.CHANNELS = 2
        self.FREQ_DATA_MASK = 0x1F
        self.BITS = 8

        # Stella addresses:
        # Ctrl0: 0x15, Ctrl1: 0x16, Freq0: 0x17, Freq1: 0x18, Vol0: 0x19, Vol1: 0x1A

        self.clocks = clocks
        self._channels = [TIAChannelState(), TIAChannelState()]
        self._sample_remainder = 0


    def get_save_state(self):
        return {
            'channels': [
                {
                    'audio_ctrl': channel.audio_ctrl,
                    'audio_freq': channel.audio_freq,
                    'audio_vol': channel.audio_vol,
                    'poly4_state': channel.poly4_state,
                    'poly5_state': channel.poly5_state,
                    'freq_phase': channel.freq_phase,
                }
                for channel in self._channels
            ],
            'sample_remainder': self._sample_remainder,
        }

    def set_save_state(self, state):
        channels = state.get('channels', [])
        for idx, channel_state in enumerate(channels):
            if idx >= len(self._channels):
                break
            channel = self._channels[idx]
            channel.audio_ctrl = channel_state.get('audio_ctrl', channel.audio_ctrl)
            channel.audio_freq = channel_state.get('audio_freq', channel.audio_freq)
            channel.audio_vol = channel_state.get('audio_vol', channel.audio_vol)
            channel.poly4_state = channel_state.get('poly4_state', channel.poly4_state)
            channel.poly5_state = channel_state.get('poly5_state', channel.poly5_state)
            channel.freq_phase = channel_state.get('freq_phase', channel.freq_phase)
        self._sample_remainder = state.get('sample_remainder', self._sample_remainder)

    # Clock poly 4, return new poly4 state
    @staticmethod
    def poly4(audio_ctrl, poly5_state, poly4_state):

        i = not (audio_ctrl & 0xF) or  \
            (not (audio_ctrl & 0xC) and (((poly4_state & 0x3) != 0x3) and (poly4_state & 0x3) and ((poly4_state & 0xF) != 0xA))) or \
            (((audio_ctrl & 0xC) == 0xC) and  (poly4_state & 0xC) and not(poly4_state & 0x2)) or \
            (((audio_ctrl & 0xC) == 0x4) and not(poly4_state & 0x8)) or \
            (((audio_ctrl & 0xC) == 0x8) and not(poly5_state & 0x1))

        poly4Output = (0x7 ^ (poly4_state >> 1)) | i << 3

        return poly4Output

    # Clock poly 5, return new poly5 state
    @staticmethod
    def poly5(audio_ctrl, poly5_state, poly4_state):

        in_5 =    not(audio_ctrl & 0xF) or \
                  (((audio_ctrl & 0x3) or ((poly4_state & 0xF) == 0xA)) and not(poly5_state & 0x1F)) or \
                  not((((audio_ctrl & 0x3) or not(poly4_state & 0x1)) and (not(poly5_state & 0x8) or not(audio_ctrl & 0x3))) ^ (poly5_state & 0x1))

        poly5Output = (poly5_state >> 1) | (in_5 << 4)

        return poly5Output

    @staticmethod
    def poly5clk(audio_ctrl, poly5_state):
        clockoutput = (((audio_ctrl & 0x3) != 0x2) or (0x2 == (poly5_state & 0x1E))) and \
                      (((audio_ctrl & 0x3) != 0x3) or (poly5_state & 0x1))

        return clockoutput


    def get_channel_data(self, channel, length):
        """Generate audio samples for a given channel.

        This follows the Stella-style state machine using polynomial counters
        (poly4/poly5) and the TIA audio control registers.
        """
        length = int(length)
        stream = [0] * length
        channel_state = self._channels[channel]

        for i in range(length):
            channel_state.freq_phase += 1
            if channel_state.freq_phase >= (channel_state.audio_freq + 1):
                channel_state.freq_phase = 0
                next_poly5 = self.poly5(
                    channel_state.audio_ctrl,
                    channel_state.poly5_state,
                    channel_state.poly4_state,
                )

                if self.poly5clk(channel_state.audio_ctrl, channel_state.poly5_state):
                    channel_state.poly4_state = self.poly4(
                        channel_state.audio_ctrl,
                        channel_state.poly5_state,
                        channel_state.poly4_state,
                    )

                channel_state.poly5_state = next_poly5

            if channel_state.poly4_state & 1:
                stream[i] = (channel_state.audio_vol & 0xF) * 0x7 & 0xFF

        return stream

    
    # Update the current state of the emulated sound data before control
    # change, so previous wave form can be stopped at correct time before
    # control change.

    def write_audio_ctrl_0(self, data):
        self.pre_write_generate_sound()
        self._channels[0].audio_ctrl = data & 0xFF
        self.post_write_generate_sound()

    def write_audio_ctrl_1(self, data):
        self.pre_write_generate_sound()
        self._channels[1].audio_ctrl = data & 0xFF
        self.post_write_generate_sound()

    def write_audio_freq_0(self, data):
        self.pre_write_generate_sound()
        self._channels[0].audio_freq = data & self.FREQ_DATA_MASK
        self.post_write_generate_sound()

    def write_audio_freq_1(self, data):
        self.pre_write_generate_sound()
        self._channels[1].audio_freq = data & self.FREQ_DATA_MASK
        self.post_write_generate_sound()

    def write_audio_vol_0(self, data):
        self.pre_write_generate_sound()
        self._channels[0].audio_vol = data
        self.post_write_generate_sound()

    def write_audio_vol_1(self, data):
        self.pre_write_generate_sound()
        self._channels[1].audio_vol = data
        self.post_write_generate_sound()

    def step(self):
        pass

    def pre_write_generate_sound(self):
        pass

    def post_write_generate_sound(self):
        pass

    def handle_events(self, event):
        pass

    def samples_from_ticks(self, ticks):
        """Convert CPU clocks into audio samples using fixed-point math."""
        self._sample_remainder += ticks * self.SAMPLERATE
        sample_count = self._sample_remainder // self.CPU_CLOCK_RATE
        self._sample_remainder = self._sample_remainder % self.CPU_CLOCK_RATE
        return int(sample_count)

class Stretch(object):
    def __init__(self):
        self.divisor           = 1000
        self.rate              =  200
        self.remainder         =    0
        self.source_pos_offset =    0

    def stretch(self, unstretched_source):
        # Maintain a source offset, if stretch is actually 'condense'
        source_pos = self.source_pos_offset
        stretched_result = []
        while source_pos < len(unstretched_source):

            if source_pos < len(unstretched_source):
                stretched_result.append(unstretched_source[source_pos])
            else:
                self.source_pos_offset = source_pos - len(unstretched_source)

            self.remainder += self.rate

            increment = int(self.remainder/self.divisor)
            self.remainder = self.remainder%self.divisor

            source_pos += increment

        return stretched_result
