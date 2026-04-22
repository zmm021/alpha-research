from collections import deque
import numpy as np


class RollingZScore:
    def __init__(self, window):
        self.window = window
        self.buffer = deque(maxlen=window)

    def warmup(self, series):
        for v in series:
            self.update(v)

    def update(self, value):
        self.buffer.append(value)

        if len(self.buffer) < 2:
            return 0.0

        arr = np.array(self.buffer)
        std = arr.std()

        if std == 0:
            return 0.0

        return (value - arr.mean()) / std
    @property
    def value(self):
        if len(self.buffer) < 2:
            return 0.0

        arr = np.array(self.buffer)
        std = arr.std()

        if std == 0:
            return 0.0

        return float((arr[-1] - arr.mean()) / std)


class RollingMean:
    def __init__(self, window):
        self.window = window
        self.buffer = deque(maxlen=window)

    def warmup(self, series):
        for v in series:
            self.update(v)

    def update(self, value):
        self.buffer.append(value)
        return float(np.mean(self.buffer))

    @property
    def value(self):
        if not self.buffer:
            return 0.0
        return float(sum(self.buffer) / len(self.buffer))


class RollingMomentum:
    def __init__(self, window):
        self.window = window
        self.buffer = deque(maxlen=window)

    def warmup(self, series):
        for v in series:
            self.update(v)

    def update(self, value):
        self.buffer.append(value)

        if len(self.buffer) < self.window:
            return 0.0

        return value - self.buffer[0]
    @property
    def value(self):
        if len(self.buffer) < self.window:
            return 0.0
        return float(self.buffer[-1] - self.buffer[0])

class RollingStd:
    def __init__(self, window):
        self.window = window
        self.buffer = deque(maxlen=window)

    def warmup(self, series):
        for v in series:
            self.update(v)

    def update(self, value):
        self.buffer.append(value)
        if len(self.buffer) < 2:
            return 0.0
        return float(np.std(self.buffer))
    @property
    def value(self):
        if len(self.buffer) < 2:
            return 0.0
        return float(np.std(self.buffer))

class RollingSum:
    def __init__(self, window):
        self.window = window
        self.buffer = deque(maxlen=window)
        self.running_sum = 0.0

    def warmup(self, series):
        for v in series:
            self.update(v)

    def update(self, value):
        if len(self.buffer) == self.window:
            self.running_sum -= self.buffer[0]
        self.buffer.append(value)
        self.running_sum += value
        return self.running_sum
    @property
    def value(self):
        return float(self.running_sum)
class RollingMax:
    def __init__(self, window):
        self.window = window
        self.buffer = deque(maxlen=window)

    def warmup(self, series):
        for v in series:
            self.update(v)

    def update(self, value):
        self.buffer.append(value)
        return float(max(self.buffer)) if self.buffer else 0.0
    @property
    def value(self):
        return float(max(self.buffer)) if self.buffer else 0.0
class RollingMin:
    def __init__(self, window):
        self.window = window
        self.buffer = deque(maxlen=window)

    def warmup(self, series):
        for v in series:
            self.update(v)

    def update(self, value):
        self.buffer.append(value)
        return float(min(self.buffer)) if self.buffer else 0.0
    @property
    def value(self):
        return float(min(self.buffer)) if self.buffer else 0.0

class EMA:
    def __init__(self, span):
        self.span = span
        self.alpha = 2.0 / (span + 1.0)
        self._value = None

    def warmup(self, series):
        for v in series:
            self.update(v)

    def update(self, value):
        value = float(value)
        if self._value is None:
            self._value = value
        else:
            self._value = self.alpha * value + (1 - self.alpha) * self._value
        return self.value

    @property
    def value(self):
        return 0.0 if self._value is None else float(self._value)
 
class RollingSlope:
    def __init__(self, window):
        self.window = window
        self.buffer = deque(maxlen=window)

    def warmup(self, series):
        for v in series:
            self.update(v)

    def update(self, value):
        self.buffer.append(float(value))

        if len(self.buffer) < 2:
            return 0.0

        y = np.array(self.buffer, dtype=float)
        x = np.arange(len(y), dtype=float)

        x_mean = x.mean()
        y_mean = y.mean()

        denom = ((x - x_mean) ** 2).sum()
        if denom == 0:
            return 0.0

        slope = ((x - x_mean) * (y - y_mean)).sum() / denom
        return float(slope)
    @property
    def value(self):
        if len(self.buffer) < 2:
            return 0.0

        y = np.array(self.buffer, dtype=float)
        x = np.arange(len(y), dtype=float)

        x_mean = x.mean()
        y_mean = y.mean()

        denom = ((x - x_mean) ** 2).sum()
        if denom == 0:
            return 0.0

        slope = ((x - x_mean) * (y - y_mean)).sum() / denom
        return float(slope)


class RollingATR:
    def __init__(self, window: int):
        self.window = window
        self.tr_buffer = deque(maxlen=window)
        self.prev_close = None

    def warmup(self, high_series, low_series, close_series):
        """
        用历史序列初始化
        """
        for h, l, c in zip(high_series, low_series, close_series):
            self.update(h, l, c)

    def update(self, high, low, close):
        high = float(high)
        low = float(low)
        close = float(close)

        if self.prev_close is None:
            tr = high - low
        else:
            tr = max(
                high - low,
                abs(high - self.prev_close),
                abs(low - self.prev_close),
            )

        self.tr_buffer.append(tr)
        self.prev_close = close

        return self.value

    @property
    def value(self):
        if not self.tr_buffer:
            return 0.0
        return sum(self.tr_buffer) / len(self.tr_buffer)