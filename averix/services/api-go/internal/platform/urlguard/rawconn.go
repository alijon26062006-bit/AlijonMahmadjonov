package urlguard

import "syscall"

// syscallRawConn aliases syscall.RawConn so the SafeDialer Control signature
// reads clearly at the call site.
type syscallRawConn = syscall.RawConn
