import org.apache.pdfbox.io.RandomAccessReadBuffer;
import org.apache.pdfbox.io.RandomAccessReadView;

/**
 * Differential fuzz probe for the RandomAccessReadBuffer + RandomAccessReadView
 * edge operation sequences NOT pinned by the wave-1482 closed/seek probe or the
 * wave-1496 default-method probe.
 *
 * Angles fuzzed here:
 *   - read() single byte exactly at EOF and after EOF (-> -1, no throw)
 *   - read(byte[],off,len) with len straddling EOF (partial count)
 *   - read(byte[],off,len) starting AT EOF (-> -1)
 *   - seek(length) (legal, EOF) vs seek(length+1) (clamp) vs seek(-1) (throw)
 *   - rewind(more-than-position) -> seek(negative) -> throw
 *   - skip(past EOF) clamps; skip after already at EOF
 *   - peek() at EOF leaves position; peek() one-before-EOF
 *   - available() after a clamped past-end seek
 *   - createView(offset+length exceeding parent): read past parent EOF inside
 *     the view (partial bulk + single -1 with position/ isEOF observation)
 *   - createView at the very end of the parent (zero readable)
 *   - view seek(length) / seek(length+1) clamp; view rewind across its origin
 *   - view read(byte[],off,len) clipped to view's available()
 *   - double-close buffer then operate (-> throw); view close then operate
 *
 * One key=value line per observation on stdout. Exceptions are projected as the
 * fully-qualified exception class name so the Python side can map it.
 */
public class RandomAccessReadFuzzProbe
{
    static String exc(Throwable t)
    {
        return t.getClass().getName();
    }

    static byte[] iso(String s) throws Exception
    {
        return s.getBytes("ISO-8859-1");
    }

    public static void main(String[] args) throws Exception
    {
        // =================================================================
        // RandomAccessReadBuffer over "0123456789" (length 10)
        // =================================================================
        {
            RandomAccessReadBuffer b = new RandomAccessReadBuffer(iso("0123456789"));

            // read single byte exactly at EOF and after EOF
            b.seek(10);
            System.out.println("buf.readAtEOF=" + b.read());
            System.out.println("buf.readAtEOF.pos=" + b.getPosition());
            System.out.println("buf.readAfterEOF=" + b.read());

            // read(byte[],off,len) straddling EOF: pos 8, ask 5 -> 2 available
            b.seek(8);
            byte[] dst = new byte[5];
            System.out.println("buf.readStraddle=" + b.read(dst, 0, 5));
            System.out.println("buf.readStraddle.bytes=" + new String(dst, 0, 2, "ISO-8859-1"));
            System.out.println("buf.readStraddle.pos=" + b.getPosition());

            // read(byte[],off,len) starting AT EOF
            byte[] dst2 = new byte[4];
            System.out.println("buf.readArrAtEOF=" + b.read(dst2, 0, 4));

            // read(byte[],off,len) with an internal offset
            b.seek(0);
            byte[] dst3 = new byte[8];
            System.out.println("buf.readArrOff=" + b.read(dst3, 3, 4));
            System.out.println("buf.readArrOff.bytes=" + new String(dst3, 3, 4, "ISO-8859-1"));
            System.out.println("buf.readArrOff.pos=" + b.getPosition());

            // seek to length (legal EOF), past length (clamp), negative (throw)
            b.seek(10);
            System.out.println("buf.seekLen.pos=" + b.getPosition());
            System.out.println("buf.seekLen.isEOF=" + b.isEOF());
            b.seek(11);
            System.out.println("buf.seekPastLen.pos=" + b.getPosition());
            try { b.seek(-1); System.out.println("buf.seekNeg=NO_THROW"); }
            catch (Exception e) { System.out.println("buf.seekNeg=" + exc(e)); }

            // rewind more than current position -> seek negative -> throw
            b.seek(3);
            try { b.rewind(5); System.out.println("buf.rewindOverPos=NO_THROW pos=" + b.getPosition()); }
            catch (Exception e) { System.out.println("buf.rewindOverPos=" + exc(e)); }

            // skip past EOF clamps; skip again at EOF stays
            b.seek(7);
            b.skip(100);
            System.out.println("buf.skipPastEOF.pos=" + b.getPosition());
            b.skip(100);
            System.out.println("buf.skipAtEOFagain.pos=" + b.getPosition());

            // peek at EOF and one-before-EOF
            b.seek(10);
            System.out.println("buf.peekEOF=" + b.peek());
            System.out.println("buf.peekEOF.pos=" + b.getPosition());
            b.seek(9);
            System.out.println("buf.peekLast=" + b.peek());
            System.out.println("buf.peekLast.pos=" + b.getPosition());

            // available after clamped past-end seek
            b.seek(100);
            System.out.println("buf.availPastEnd=" + b.available());
            b.seek(6);
            System.out.println("buf.availMid=" + b.available());

            // double close then operate
            b.close();
            b.close(); // idempotent
            System.out.println("buf.isClosed=" + b.isClosed());
            try { b.read(); System.out.println("buf.readClosed=NO_THROW"); }
            catch (Exception e) { System.out.println("buf.readClosed=" + exc(e)); }
            try { b.length(); System.out.println("buf.lengthClosed=NO_THROW"); }
            catch (Exception e) { System.out.println("buf.lengthClosed=" + exc(e)); }
        }

        // =================================================================
        // RandomAccessReadView over "0123456789" parent: view [4, 10) but the
        // declared length (10) exceeds the parent's remaining bytes (6) so the
        // view runs off the parent before its own logical end.
        // =================================================================
        {
            RandomAccessReadBuffer parent = new RandomAccessReadBuffer(iso("0123456789"));
            RandomAccessReadView v = parent.createView(4, 10); // claims 10, only 6 left in parent

            System.out.println("view.length=" + v.length());
            System.out.println("view.avail0=" + v.available());

            // bulk read of the whole claimed length -> partial (6 from parent)
            byte[] dst = new byte[10];
            int n = v.read(dst, 0, 10);
            System.out.println("view.readAll=" + n);
            System.out.println("view.readAll.bytes=" + new String(dst, 0, Math.max(n, 0), "ISO-8859-1"));
            System.out.println("view.readAll.pos=" + v.getPosition());
            System.out.println("view.readAll.isEOF=" + v.isEOF());
            System.out.println("view.readAll.readAfter=" + v.read());

            v.close();
        }

        // =================================================================
        // RandomAccessReadView wholly inside parent: parent "0123456789",
        // view [2, 4) covers "2345".
        // =================================================================
        {
            RandomAccessReadBuffer parent = new RandomAccessReadBuffer(iso("0123456789"));
            RandomAccessReadView v = parent.createView(2, 4); // "2345"

            // read past view bounded length one byte at a time
            int[] vals = new int[6];
            for (int i = 0; i < 6; i++) vals[i] = v.read();
            StringBuilder sb = new StringBuilder();
            for (int i = 0; i < 6; i++) { if (i > 0) sb.append(','); sb.append(vals[i]); }
            System.out.println("view.in.singleReads=" + sb);
            System.out.println("view.in.pos=" + v.getPosition());
            System.out.println("view.in.isEOF=" + v.isEOF());

            // seek to view length (EOF), past view length (clamp), negative (throw)
            v.seek(4);
            System.out.println("view.in.seekLen.pos=" + v.getPosition());
            System.out.println("view.in.seekLen.isEOF=" + v.isEOF());
            v.seek(100);
            System.out.println("view.in.seekPast.pos=" + v.getPosition());
            try { v.seek(-1); System.out.println("view.in.seekNeg=NO_THROW"); }
            catch (Exception e) { System.out.println("view.in.seekNeg=" + exc(e)); }

            // read(byte[],off,len) clipped to view available: seek 1, ask 10 -> 3
            v.seek(1);
            byte[] dst = new byte[10];
            System.out.println("view.in.readClip=" + v.read(dst, 0, 10));
            System.out.println("view.in.readClip.bytes=" + new String(dst, 0, 3, "ISO-8859-1"));
            System.out.println("view.in.readClip.pos=" + v.getPosition());

            // rewind across origin -> parent seek negative -> throw
            v.seek(2);
            try { v.rewind(5); System.out.println("view.in.rewindOver=NO_THROW pos=" + v.getPosition()); }
            catch (Exception e) { System.out.println("view.in.rewindOver=" + exc(e)); }

            // peek at view EOF / mid
            v.seek(4);
            System.out.println("view.in.peekEOF=" + v.peek());
            v.seek(1);
            System.out.println("view.in.peekMid=" + v.peek());
            System.out.println("view.in.peekMid.pos=" + v.getPosition());

            // nested createView forbidden
            try { v.createView(0, 1); System.out.println("view.in.nested=NO_THROW"); }
            catch (Exception e) { System.out.println("view.in.nested=" + exc(e)); }

            // close (closeInput defaults false) then operate
            v.close();
            System.out.println("view.in.isClosed=" + v.isClosed());
            try { v.read(); System.out.println("view.in.readClosed=NO_THROW"); }
            catch (Exception e) { System.out.println("view.in.readClosed=" + exc(e)); }
            try { v.length(); System.out.println("view.in.lengthClosed=NO_THROW"); }
            catch (Exception e) { System.out.println("view.in.lengthClosed=" + exc(e)); }

            parent.close();
        }

        // =================================================================
        // View created at the very end of the parent: zero readable bytes.
        // =================================================================
        {
            RandomAccessReadBuffer parent = new RandomAccessReadBuffer(iso("0123456789"));
            RandomAccessReadView v = parent.createView(10, 2); // origin at parent EOF
            System.out.println("view.end.length=" + v.length());
            System.out.println("view.end.isEOF=" + v.isEOF());
            System.out.println("view.end.read=" + v.read());
            byte[] dst = new byte[2];
            System.out.println("view.end.readArr=" + v.read(dst, 0, 2));
            v.close();
            parent.close();
        }
    }
}
