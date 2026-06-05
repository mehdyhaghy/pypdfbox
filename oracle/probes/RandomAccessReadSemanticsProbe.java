import org.apache.pdfbox.io.RandomAccessReadBuffer;
import org.apache.pdfbox.io.RandomAccessReadBufferedFile;
import org.apache.pdfbox.io.RandomAccessReadView;
import org.apache.pdfbox.io.SequenceRandomAccessRead;
import org.apache.pdfbox.io.RandomAccessRead;

import java.io.File;
import java.io.FileOutputStream;
import java.util.Arrays;

/**
 * Differential probe for the RandomAccessRead family closed/seek semantics.
 * Prints, per class, the exception class + message thrown on:
 *   - seek(-1)               (negative seek)
 *   - read() after close()   (operation after close)
 * Plus a couple of EOF/seek-past-end observations.
 */
public class RandomAccessReadSemanticsProbe
{
    static String desc(Throwable t)
    {
        return t.getClass().getName() + "|" + t.getMessage();
    }

    public static void main(String[] args) throws Exception
    {
        // ---- RandomAccessReadBuffer ----
        {
            RandomAccessReadBuffer b = new RandomAccessReadBuffer("abc".getBytes("ISO-8859-1"));
            try { b.seek(-1); System.out.println("buf.seekNeg=NO_THROW"); }
            catch (Exception e) { System.out.println("buf.seekNeg=" + desc(e)); }

            // seek past end then read
            b.seek(100);
            System.out.println("buf.seekPastEnd.pos=" + b.getPosition());
            System.out.println("buf.seekPastEnd.isEOF=" + b.isEOF());
            System.out.println("buf.seekPastEnd.read=" + b.read());

            b.close();
            try { b.read(); System.out.println("buf.readClosed=NO_THROW"); }
            catch (Exception e) { System.out.println("buf.readClosed=" + desc(e)); }
            try { b.seek(0); System.out.println("buf.seekClosed=NO_THROW"); }
            catch (Exception e) { System.out.println("buf.seekClosed=" + desc(e)); }
            try { b.getPosition(); System.out.println("buf.getPosClosed=NO_THROW"); }
            catch (Exception e) { System.out.println("buf.getPosClosed=" + desc(e)); }
            try { b.length(); System.out.println("buf.lengthClosed=NO_THROW"); }
            catch (Exception e) { System.out.println("buf.lengthClosed=" + desc(e)); }
        }

        // ---- RandomAccessReadBufferedFile ----
        {
            File f = File.createTempFile("rarbf", ".bin");
            try (FileOutputStream fos = new FileOutputStream(f)) { fos.write("abc".getBytes("ISO-8859-1")); }
            RandomAccessReadBufferedFile bf = new RandomAccessReadBufferedFile(f);
            try { bf.seek(-1); System.out.println("file.seekNeg=NO_THROW"); }
            catch (Exception e) { System.out.println("file.seekNeg=" + desc(e)); }

            bf.seek(100);
            System.out.println("file.seekPastEnd.pos=" + bf.getPosition());
            System.out.println("file.seekPastEnd.isEOF=" + bf.isEOF());
            System.out.println("file.seekPastEnd.read=" + bf.read());

            bf.close();
            try { bf.read(); System.out.println("file.readClosed=NO_THROW"); }
            catch (Exception e) { System.out.println("file.readClosed=" + desc(e)); }
            try { bf.seek(0); System.out.println("file.seekClosed=NO_THROW"); }
            catch (Exception e) { System.out.println("file.seekClosed=" + desc(e)); }
            try { bf.length(); System.out.println("file.lengthClosed=NO_THROW"); }
            catch (Exception e) { System.out.println("file.lengthClosed=" + desc(e)); }
            f.delete();
        }

        // ---- SequenceRandomAccessRead ----
        {
            RandomAccessRead r1 = new RandomAccessReadBuffer("abc".getBytes("ISO-8859-1"));
            RandomAccessRead r2 = new RandomAccessReadBuffer("de".getBytes("ISO-8859-1"));
            SequenceRandomAccessRead s = new SequenceRandomAccessRead(Arrays.asList(r1, r2));
            System.out.println("seq.length=" + s.length());
            try { s.seek(-1); System.out.println("seq.seekNeg=NO_THROW"); }
            catch (Exception e) { System.out.println("seq.seekNeg=" + desc(e)); }
            s.seek(4); // into 2nd segment
            System.out.println("seq.seekMid.read=" + s.read());
            s.close();
            try { s.read(); System.out.println("seq.readClosed=NO_THROW"); }
            catch (Exception e) { System.out.println("seq.readClosed=" + desc(e)); }
            try { s.seek(0); System.out.println("seq.seekClosed=NO_THROW"); }
            catch (Exception e) { System.out.println("seq.seekClosed=" + desc(e)); }
        }

        // ---- RandomAccessReadView ----
        {
            RandomAccessReadBuffer parent = new RandomAccessReadBuffer("abcdefgh".getBytes("ISO-8859-1"));
            RandomAccessReadView v = new RandomAccessReadView(parent, 2, 4); // covers cdef
            try { v.seek(-1); System.out.println("view.seekNeg=NO_THROW"); }
            catch (Exception e) { System.out.println("view.seekNeg=" + desc(e)); }
            v.seek(0);
            System.out.println("view.read0=" + v.read());
            v.close();
            try { v.read(); System.out.println("view.readClosed=NO_THROW"); }
            catch (Exception e) { System.out.println("view.readClosed=" + desc(e)); }
            try { v.seek(0); System.out.println("view.seekClosed=NO_THROW"); }
            catch (Exception e) { System.out.println("view.seekClosed=" + desc(e)); }
            try { v.length(); System.out.println("view.lengthClosed=NO_THROW"); }
            catch (Exception e) { System.out.println("view.lengthClosed=" + desc(e)); }
        }
    }
}
