from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class State(_message.Message):
    __slots__ = ("term", "isLeader")
    TERM_FIELD_NUMBER: _ClassVar[int]
    ISLEADER_FIELD_NUMBER: _ClassVar[int]
    term: int
    isLeader: bool
    def __init__(self, term: _Optional[int] = ..., isLeader: bool = ...) -> None: ...

class KeyValue(_message.Message):
    __slots__ = ("key", "value", "ClientId", "RequestId")
    KEY_FIELD_NUMBER: _ClassVar[int]
    VALUE_FIELD_NUMBER: _ClassVar[int]
    CLIENTID_FIELD_NUMBER: _ClassVar[int]
    REQUESTID_FIELD_NUMBER: _ClassVar[int]
    key: str
    value: str
    ClientId: int
    RequestId: int
    def __init__(self, key: _Optional[str] = ..., value: _Optional[str] = ..., ClientId: _Optional[int] = ..., RequestId: _Optional[int] = ...) -> None: ...

class GetKey(_message.Message):
    __slots__ = ("key", "ClientId", "RequestId")
    KEY_FIELD_NUMBER: _ClassVar[int]
    CLIENTID_FIELD_NUMBER: _ClassVar[int]
    REQUESTID_FIELD_NUMBER: _ClassVar[int]
    key: str
    ClientId: int
    RequestId: int
    def __init__(self, key: _Optional[str] = ..., ClientId: _Optional[int] = ..., RequestId: _Optional[int] = ...) -> None: ...

class Reply(_message.Message):
    __slots__ = ("wrongLeader", "error", "value")
    WRONGLEADER_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    VALUE_FIELD_NUMBER: _ClassVar[int]
    wrongLeader: bool
    error: str
    value: str
    def __init__(self, wrongLeader: bool = ..., error: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...

class IntegerArg(_message.Message):
    __slots__ = ("arg",)
    ARG_FIELD_NUMBER: _ClassVar[int]
    arg: int
    def __init__(self, arg: _Optional[int] = ...) -> None: ...

class StringArg(_message.Message):
    __slots__ = ("arg",)
    ARG_FIELD_NUMBER: _ClassVar[int]
    arg: str
    def __init__(self, arg: _Optional[str] = ...) -> None: ...

class Empty(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class GenericResponse(_message.Message):
    __slots__ = ("success",)
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    success: bool
    def __init__(self, success: bool = ...) -> None: ...

class RequestVoteRequest(_message.Message):
    __slots__ = ("term", "candidateId", "lastLogIndex", "lastLogTerm")
    TERM_FIELD_NUMBER: _ClassVar[int]
    CANDIDATEID_FIELD_NUMBER: _ClassVar[int]
    LASTLOGINDEX_FIELD_NUMBER: _ClassVar[int]
    LASTLOGTERM_FIELD_NUMBER: _ClassVar[int]
    term: int
    candidateId: int
    lastLogIndex: int
    lastLogTerm: int
    def __init__(self, term: _Optional[int] = ..., candidateId: _Optional[int] = ..., lastLogIndex: _Optional[int] = ..., lastLogTerm: _Optional[int] = ...) -> None: ...

class RequestVoteResponse(_message.Message):
    __slots__ = ("term", "voteGranted")
    TERM_FIELD_NUMBER: _ClassVar[int]
    VOTEGRANTED_FIELD_NUMBER: _ClassVar[int]
    term: int
    voteGranted: bool
    def __init__(self, term: _Optional[int] = ..., voteGranted: bool = ...) -> None: ...

class Entry(_message.Message):
    __slots__ = ("term", "key", "value")
    TERM_FIELD_NUMBER: _ClassVar[int]
    KEY_FIELD_NUMBER: _ClassVar[int]
    VALUE_FIELD_NUMBER: _ClassVar[int]
    term: int
    key: str
    value: str
    def __init__(self, term: _Optional[int] = ..., key: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...

class AppendEntriesRequest(_message.Message):
    __slots__ = ("term", "leaderId", "prevLogIndex", "prevLogTerm", "entries", "leaderCommit")
    TERM_FIELD_NUMBER: _ClassVar[int]
    LEADERID_FIELD_NUMBER: _ClassVar[int]
    PREVLOGINDEX_FIELD_NUMBER: _ClassVar[int]
    PREVLOGTERM_FIELD_NUMBER: _ClassVar[int]
    ENTRIES_FIELD_NUMBER: _ClassVar[int]
    LEADERCOMMIT_FIELD_NUMBER: _ClassVar[int]
    term: int
    leaderId: int
    prevLogIndex: int
    prevLogTerm: int
    entries: _containers.RepeatedCompositeFieldContainer[Entry]
    leaderCommit: int
    def __init__(self, term: _Optional[int] = ..., leaderId: _Optional[int] = ..., prevLogIndex: _Optional[int] = ..., prevLogTerm: _Optional[int] = ..., entries: _Optional[_Iterable[_Union[Entry, _Mapping]]] = ..., leaderCommit: _Optional[int] = ...) -> None: ...

class AppendEntriesResponse(_message.Message):
    __slots__ = ("term", "success")
    TERM_FIELD_NUMBER: _ClassVar[int]
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    term: int
    success: bool
    def __init__(self, term: _Optional[int] = ..., success: bool = ...) -> None: ...
