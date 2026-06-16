import org.apache.pdfbox.io.RandomAccessReadWriteBuffer;
import org.apache.pdfbox.io.ScratchFile;
import org.apache.pdfbox.io.RandomAccess;

/**
 * Differential fuzz probe for the WRITE side of the RandomAccess family
 * (wave 1558). The wave-1483 RandomAccessWriteScratchSemanticsProbe pinned the
 * closed-state / negative-seek exceptions; this probe fuzzes the *write/read
 * round-trip operation sequences* those probes left open:
 *
 *   - write(int) single bytes then seek(0)+read back
 *   - write(byte[], off, len) with off/len edges (whole, sub-slice, len==0)
 *   - seek into the middle then overwrite (in-place patch); length unchanged
 *   - seek past current length then write (gap behaviour: throw? zero-fill?)
 *   - clear() then length()/position()/read()
 *   - interleave write / seek / read
 *   - write spanning a scratch page boundary (ScratchFileBuffer, 4KB pages)
 *   - length() / getPosition() after various ops
 *   - read() at EOF after writes
 *
 * One key=value line per observation on stdout. Exceptions are projected as the
 * fully-qualified exception class name so the Python side can map it.
 */
public class RandomAccessWriteFuzzProbe
{
    static String exc(Throwable t)
    {
        return t.getClass().getName();
    }

    static byte[] iso(String s) throws Exception
    {
        return s.getBytes("ISO-8859-1");
    }

    // Drain whole buffer from position 0 as a decimal-comma list of unsigned bytes.
    static String drain(RandomAccess r) throws Exception
    {
        long save = r.getPosition();
        r.seek(0);
        StringBuilder sb = new StringBuilder();
        int b;
        boolean first = true;
        while ((b = r.read()) != -1)
        {
            if (!first) sb.append(',');
            sb.append(b);
            first = false;
        }
        r.seek(save);
        return sb.toString();
    }

    public static void main(String[] args) throws Exception
    {
        // =================================================================
        // RandomAccessReadWriteBuffer — single-byte write then read-back
        // =================================================================
        {
            RandomAccessReadWriteBuffer w = new RandomAccessReadWriteBuffer();
            w.write('A'); w.write('B'); w.write('C');
            System.out.println("rwb.afterWrite.len=" + w.length());
            System.out.println("rwb.afterWrite.pos=" + w.getPosition());
            w.seek(0);
            System.out.println("rwb.read0=" + w.read());
            System.out.println("rwb.read1=" + w.read());
            System.out.println("rwb.read2=" + w.read());
            System.out.println("rwb.readEOF=" + w.read());
            System.out.println("rwb.eof.pos=" + w.getPosition());
            w.close();
        }

        // =================================================================
        // write(byte[], off, len) edges
        // =================================================================
        {
            RandomAccessReadWriteBuffer w = new RandomAccessReadWriteBuffer();
            byte[] src = iso("0123456789");
            w.write(src, 2, 4); // "2345"
            System.out.println("rwb.partial.len=" + w.length());
            System.out.println("rwb.partial.bytes=" + drain(w));
            // len == 0 write: no-op
            w.write(src, 0, 0);
            System.out.println("rwb.zerolen.len=" + w.length());
            System.out.println("rwb.zerolen.pos=" + w.getPosition());
            // full array
            w.write(src);
            System.out.println("rwb.full.len=" + w.length());
            w.close();
        }

        // =================================================================
        // seek-to-middle overwrite (in-place patch) — length must not change
        // =================================================================
        {
            RandomAccessReadWriteBuffer w = new RandomAccessReadWriteBuffer();
            w.write(iso("ABCDEF"));
            w.seek(2);
            w.write('x'); w.write('y');
            System.out.println("rwb.patch.len=" + w.length());
            System.out.println("rwb.patch.pos=" + w.getPosition());
            System.out.println("rwb.patch.bytes=" + drain(w));
            w.close();
        }

        // =================================================================
        // seek PAST end then write — gap behaviour
        // =================================================================
        {
            RandomAccessReadWriteBuffer w = new RandomAccessReadWriteBuffer();
            w.write(iso("AB")); // len 2
            try
            {
                w.seek(5);
                System.out.println("rwb.seekPast.pos=" + w.getPosition());
                System.out.println("rwb.seekPast.len=" + w.length());
                w.write('Z');
                System.out.println("rwb.gapWrite.len=" + w.length());
                System.out.println("rwb.gapWrite.pos=" + w.getPosition());
                System.out.println("rwb.gapWrite.bytes=" + drain(w));
            }
            catch (Exception e)
            {
                System.out.println("rwb.seekPastWrite=" + exc(e));
            }
            w.close();
        }

        // =================================================================
        // length() after seek-past-end WITHOUT writing
        // =================================================================
        {
            RandomAccessReadWriteBuffer w = new RandomAccessReadWriteBuffer();
            w.write(iso("AB"));
            try
            {
                w.seek(100);
                System.out.println("rwb.seekNoWrite.pos=" + w.getPosition());
                System.out.println("rwb.seekNoWrite.len=" + w.length());
            }
            catch (Exception e)
            {
                System.out.println("rwb.seekNoWrite=" + exc(e));
            }
            w.close();
        }

        // =================================================================
        // clear() then length / position / read
        // =================================================================
        {
            RandomAccessReadWriteBuffer w = new RandomAccessReadWriteBuffer();
            w.write(iso("hello"));
            w.clear();
            System.out.println("rwb.clear.len=" + w.length());
            System.out.println("rwb.clear.pos=" + w.getPosition());
            System.out.println("rwb.clear.read=" + w.read());
            // write again after clear
            w.write('Q');
            System.out.println("rwb.clearReuse.len=" + w.length());
            System.out.println("rwb.clearReuse.bytes=" + drain(w));
            w.close();
        }

        // =================================================================
        // interleave write / seek / read
        // =================================================================
        {
            RandomAccessReadWriteBuffer w = new RandomAccessReadWriteBuffer();
            w.write(iso("12345"));
            w.seek(1);
            System.out.println("rwb.inter.read1=" + w.read()); // '2'
            w.write('Z'); // overwrites index 2 ('3')
            System.out.println("rwb.inter.pos=" + w.getPosition());
            System.out.println("rwb.inter.read3=" + w.read()); // '4'
            System.out.println("rwb.inter.len=" + w.length());
            System.out.println("rwb.inter.bytes=" + drain(w));
            w.close();
        }

        // =================================================================
        // seek-then-write WITHOUT an interleaved read (the common writer path).
        // Upstream's write(int) is a *relative* ByteBuffer.put while read/seek
        // are *absolute* get(index): when no read precedes the write, the
        // ByteBuffer's relative position still tracks the logical pointer, so
        // the byte lands at the seeked position. pypdfbox (BytesIO) matches.
        // =================================================================
        {
            RandomAccessReadWriteBuffer w = new RandomAccessReadWriteBuffer();
            w.write(iso("12345"));
            w.seek(2);
            w.write('Z');
            System.out.println("rwb.seekWrite.bytes=" + drain(w));
            System.out.println("rwb.seekWrite.pos=" + w.getPosition());
            System.out.println("rwb.seekWrite.len=" + w.length());
            w.close();
        }

        // =================================================================
        // ScratchFileBuffer — page boundary spanning write (4KB pages)
        // =================================================================
        {
            ScratchFile sf = ScratchFile.getMainMemoryOnlyInstance();
            RandomAccess buf = sf.createBuffer();
            int pageSize = 4096;
            // write 4090 bytes of 'a', then 12 bytes of 'b' -> spans into page 2
            byte[] a = new byte[4090];
            java.util.Arrays.fill(a, (byte) 'a');
            byte[] b = new byte[12];
            java.util.Arrays.fill(b, (byte) 'b');
            buf.write(a);
            buf.write(b);
            System.out.println("sfb.span.len=" + buf.length());
            System.out.println("sfb.span.pos=" + buf.getPosition());
            // read back the boundary region [4088, 4102)
            buf.seek(4088);
            byte[] window = new byte[14];
            int n = buf.read(window, 0, 14);
            System.out.println("sfb.span.window.n=" + n);
            System.out.println("sfb.span.window=" + new String(window, 0, n, "ISO-8859-1"));
            // read at EOF
            buf.seek(buf.length());
            System.out.println("sfb.span.readEOF=" + buf.read());
            buf.close();
            sf.close();
        }

        // =================================================================
        // ScratchFileBuffer — seek to middle overwrite + seek past end
        // =================================================================
        {
            ScratchFile sf = ScratchFile.getMainMemoryOnlyInstance();
            RandomAccess buf = sf.createBuffer();
            buf.write(iso("ABCDEF"));
            buf.seek(2);
            buf.write('x');
            System.out.println("sfb.patch.len=" + buf.length());
            System.out.println("sfb.patch.pos=" + buf.getPosition());
            System.out.println("sfb.patch.bytes=" + drain(buf));
            // seek past end on a scratch buffer
            try
            {
                buf.seek(100);
                System.out.println("sfb.seekPast.pos=" + buf.getPosition());
                System.out.println("sfb.seekPast.len=" + buf.length());
            }
            catch (Exception e)
            {
                System.out.println("sfb.seekPast=" + exc(e));
            }
            buf.close();
            sf.close();
        }

        // =================================================================
        // ScratchFileBuffer — clear() then length / write again
        // =================================================================
        {
            ScratchFile sf = ScratchFile.getMainMemoryOnlyInstance();
            RandomAccess buf = sf.createBuffer();
            buf.write(iso("hello"));
            buf.clear();
            System.out.println("sfb.clear.len=" + buf.length());
            System.out.println("sfb.clear.pos=" + buf.getPosition());
            System.out.println("sfb.clear.read=" + buf.read());
            buf.write('Q');
            System.out.println("sfb.clearReuse.len=" + buf.length());
            System.out.println("sfb.clearReuse.bytes=" + drain(buf));
            buf.close();
            sf.close();
        }

        // =================================================================
        // double-close then write
        // =================================================================
        {
            RandomAccessReadWriteBuffer w = new RandomAccessReadWriteBuffer();
            w.write('A');
            w.close();
            w.close(); // idempotent
            try { w.write('B'); System.out.println("rwb.writeAfterClose=NO_THROW"); }
            catch (Exception e) { System.out.println("rwb.writeAfterClose=" + exc(e)); }
            try { w.clear(); System.out.println("rwb.clearAfterClose=NO_THROW"); }
            catch (Exception e) { System.out.println("rwb.clearAfterClose=" + exc(e)); }
        }

        // =================================================================
        // read()-then-write() quirk: upstream write(int) is a RELATIVE
        // ByteBuffer.put while read()/seek() are ABSOLUTE get(index). A read
        // does NOT advance the ByteBuffer's relative put position, so a write
        // that follows a read lands at the ByteBuffer's stale relative
        // position (here 0), NOT at the logical pointer. pypdfbox (BytesIO,
        // single shared cursor) writes at the logical pointer instead — an
        // honest, documented divergence on this fragile interleave that no
        // real PDFBox writer exercises.
        // =================================================================
        {
            RandomAccessReadWriteBuffer w = new RandomAccessReadWriteBuffer();
            w.write(iso("ABCDE"));
            w.seek(0);
            w.read(); // A
            w.read(); // B  -> logical pointer now 2
            w.write('z');
            System.out.println("rwb.readWrite.bytes=" + drain(w));
            System.out.println("rwb.readWrite.pos=" + w.getPosition());
            w.close();
        }
    }
}
