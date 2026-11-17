package org.residuelab.transport;
import java.io.*;
import java.nio.channels.*;
import java.util.concurrent.*;
import java.util.concurrent.locks.*;

/** One local mutex per canonical lock file, plus the OS lock shared by processes. */
public final class Coordinator {
    private static final ConcurrentHashMap<String, ReentrantLock> LOCAL = new ConcurrentHashMap<>();
    public interface Action<T> { T run() throws Exception; }
    public static <T> T call(File file, long deadline, Action<T> action) throws Exception {
        ReentrantLock local = LOCAL.computeIfAbsent(file.getCanonicalPath(), x -> new ReentrantLock(true));
        long left = deadline - System.nanoTime();
        if (left <= 0 || !local.tryLock(left, TimeUnit.NANOSECONDS)) throw new IOException("policy lock deadline");
        try (RandomAccessFile raf = new RandomAccessFile(file, "rw"); FileChannel ch = raf.getChannel()) {
            FileLock lock = null;
            while (lock == null) {
                if (System.nanoTime() >= deadline) throw new IOException("process lock deadline");
                lock = ch.tryLock();
                if (lock == null) Thread.sleep(1);
            }
            try { return action.run(); } finally { lock.release(); }
        } finally { local.unlock(); }
    }
}
