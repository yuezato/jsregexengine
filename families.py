"""The benchmark families of RegElk (benchmark_vectors.ml), written as JavaScript patterns.
Regex-size families take the nesting depth k; string-size families take the input length n.
Each entry gives the pattern, the original input of RegElk, and an input of length about n."""


def nnplus(k):          # r0 = a, rk = (?:r_{k-1})+
    r = 'a'
    for _ in range(k): r = '(?:%s)+' % r
    return r


def cdn(k):             # r0 = a|(^), rk = (?:r_{k-1})+
    r = 'a|(^)'
    for _ in range(k): r = '(?:%s)+' % r
    return r


def clocks(k):          # r0 = a, rk = (r_{k-1})*
    r = 'a'
    for _ in range(k): r = '(%s)*' % r
    return r


def lareg(k):           # r0 = (a*)b, rk = a(?=r_{k-1})
    r = '(a*)b'
    for _ in range(k): r = 'a(?=%s)' % r
    return r


def lbreg(k):           # r0 = ba*, rk = a*(?<=r_{k-1})
    r = 'ba*'
    for _ in range(k): r = 'a*(?<=%s)' % r
    return r


LASTR = 'c(?:a(?=a*(?<=c(a*))b))*'
LBSTR = 'b(?:a(?<=ba*))*'

REGEX_SIZE = {   # name: (pattern of depth k, original input, input of length n)
    'NNPlus': (nnplus, 'a' * 100, lambda n: 'a' * n),
    'CDN':    (cdn,    'b',       lambda n: 'a' * (n - 1) + 'b'),
    'Clocks': (clocks, 'a' * 100, lambda n: 'a' * n),
    'LAreg':  (lareg,  'a' * 1000 + 'b', lambda n: 'a' * (n - 1) + 'b'),
    'LBreg':  (lbreg,  'b' + 'a' * 100,  lambda n: 'b' + 'a' * (n - 1)),
}
STRING_SIZE = {  # name: (fixed pattern, input of length about n)
    'LAstr': (LASTR, lambda n: 'c' + 'a' * (n - 2) + 'b'),
    'LBstr': (LBSTR, lambda n: 'b' + 'a' * (n - 1)),
}


# Not in RegElk, whose families are all greedy: lazy versions of three of them.
# The final $ makes the leftmost match run through the whole input, so the walk does real work.

def nnplus_lazy(k):     # nested lazy plus
    r = 'a'
    for _ in range(k): r = '(?:%s)+?' % r
    return r + '$'


def cdn_lazy(k):        # nested lazy plus whose body a|(^) is nullable; copying the body would double it per level
    r = 'a|(^)'
    for _ in range(k): r = '(?:%s)+?' % r
    return r + '$'


def clocks_lazy(k):     # nested lazy star: every character re-enters all k levels
    r = 'a'
    for _ in range(k): r = '(%s)*?' % r
    return r + '$'


LAZY = {
    'NNPlus?': (nnplus_lazy, lambda n: 'a' * n),
    'CDN?':    (cdn_lazy,    lambda n: 'a' * n),
    'Clocks?': (clocks_lazy, lambda n: 'a' * n),
}
