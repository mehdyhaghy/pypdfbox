import org.apache.pdfbox.io.RandomAccessReadBuffer;
import org.apache.pdfbox.io.RandomAccessRead;
import org.apache.pdfbox.io.SequenceRandomAccessRead;

import java.util.Arrays;

/**
 * Differential probe for the DEFAULT-method semantics of
 * {@link org.apache.pdfbox.io.RandomAccessRead} that the wave-1482
 * RandomAccessReadSemanticsProbe (closed/seek) did not pin:
 *   - peek() at EOF (must not advance, returns -1)
 *   - rewind(n) past start
 *   - available() return value + its int type (upstream returns int, so a
 *     length beyond Integer range would clip — we only test small lengths)
 *   - skip(n) past end clamps to length
 *   - read(byte[]) with a zero-length array
 *   - readFully(byte[]) past EOF — exception class
 *   - isEOF() must NOT advance the position
 *   - SequenceRandomAccessRead.read(byte[],off,len) crossing a segment boundary
 *
 * One key=value per line on stdout.
 */
public class RandomAccessReadDefaultsProbe
{
    static String desc(Throwable t)
    {
        return t.getClass().getName();
    }

    public static void main(String[] args) throws Exception
    {
        // ---- peek at EOF ----
        {
            RandomAccessReadBuffer b = new RandomAccessReadBuffer("abc".getBytes("ISO-8859-1"));
            b.seek(3); // at EOF
            System.out.println("peekEOF.val=" + b.peek());
            System.out.println("peekEOF.posAfter=" + b.getPosition());
            // peek mid
            b.seek(1);
            System.out.println("peekMid.val=" + b.peek());
            System.out.println("peekMid.posAfter=" + b.getPosition());
            b.close();
        }

        // ---- rewind ----
        {
            RandomAccessReadBuffer b = new RandomAccessReadBuffer("abcde".getBytes("ISO-8859-1"));
            b.seek(2);
            try { b.rewind(5); System.out.println("rewindPastStart=NO_THROW pos=" + b.getPosition()); }
            catch (Exception e) { System.out.println("rewindPastStart=" + desc(e)); }
            b.seek(3);
            try { b.rewind(-1); System.out.println("rewindNeg=NO_THROW pos=" + b.getPosition()); }
            catch (Exception e) { System.out.println("rewindNeg=" + desc(e)); }
            b.seek(4);
            b.rewind(0);
            System.out.println("rewind0.pos=" + b.getPosition());
            b.close();
        }

        // ---- available ----
        {
            RandomAccessReadBuffer b = new RandomAccessReadBuffer("abcdefghij".getBytes("ISO-8859-1"));
            System.out.println("avail.start=" + b.available());
            b.seek(4);
            System.out.println("avail.mid=" + b.available());
            b.seek(10);
            System.out.println("avail.end=" + b.available());
            b.seek(100);
            System.out.println("avail.pastEnd=" + b.available());
            b.close();
        }

        // ---- skip ----
        {
            RandomAccessReadBuffer b = new RandomAccessReadBuffer("abcde".getBytes("ISO-8859-1"));
            b.seek(1);
            b.skip(2);
            System.out.println("skip.pos=" + b.getPosition());
            b.skip(100);
            System.out.println("skipPastEnd.pos=" + b.getPosition());
            try { b.skip(-1); System.out.println("skipNeg=NO_THROW pos=" + b.getPosition()); }
            catch (Exception e) { System.out.println("skipNeg=" + desc(e)); }
            b.close();
        }

        // ---- read(byte[]) zero-length ----
        {
            RandomAccessReadBuffer b = new RandomAccessReadBuffer("abc".getBytes("ISO-8859-1"));
            byte[] empty = new byte[0];
            System.out.println("readEmptyArr=" + b.read(empty));
            System.out.println("readEmptyArr.pos=" + b.getPosition());
            // read(byte[]) full
            byte[] dst = new byte[10];
            System.out.println("readArr=" + b.read(dst));
            // read again at EOF
            System.out.println("readArrEOF=" + b.read(dst));
            b.close();
        }

        // ---- readFully past EOF ----
        {
            RandomAccessReadBuffer b = new RandomAccessReadBuffer("abc".getBytes("ISO-8859-1"));
            byte[] dst = new byte[5];
            try { b.readFully(dst); System.out.println("readFullyPastEOF=NO_THROW"); }
            catch (Exception e) { System.out.println("readFullyPastEOF=" + desc(e)); }
            b.close();
        }

        // ---- isEOF non-advancing ----
        {
            RandomAccessReadBuffer b = new RandomAccessReadBuffer("abc".getBytes("ISO-8859-1"));
            b.seek(1);
            System.out.println("isEOF.mid=" + b.isEOF());
            System.out.println("isEOF.mid.posAfter=" + b.getPosition());
            b.seek(3);
            System.out.println("isEOF.end=" + b.isEOF());
            System.out.println("isEOF.end.posAfter=" + b.getPosition());
            b.close();
        }

        // ---- SequenceRandomAccessRead read across boundary ----
        {
            RandomAccessRead r1 = new RandomAccessReadBuffer("abc".getBytes("ISO-8859-1"));
            RandomAccessRead r2 = new RandomAccessReadBuffer("de".getBytes("ISO-8859-1"));
            SequenceRandomAccessRead s = new SequenceRandomAccessRead(Arrays.asList(r1, r2));
            s.seek(2); // last byte of seg1
            byte[] dst = new byte[5];
            int n = s.read(dst, 0, 5); // should cross into seg2
            System.out.println("seqCross.n=" + n);
            System.out.println("seqCross.bytes=" + new String(dst, 0, Math.max(n, 0), "ISO-8859-1"));
            System.out.println("seqCross.posAfter=" + s.getPosition());
            // continue reading at EOF
            System.out.println("seqCross.readAfter=" + s.read());
            System.out.println("seqCross.avail=" + s.available());
            s.close();
        }
    }
}
