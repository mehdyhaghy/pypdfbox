import org.apache.pdfbox.io.RandomAccessReadMemoryMappedFile;
import org.apache.pdfbox.io.RandomAccessReadWriteBuffer;
import org.apache.pdfbox.io.ScratchFile;
import org.apache.pdfbox.io.RandomAccess;

import java.io.File;
import java.io.FileOutputStream;

/**
 * Differential probe for the closed-state / negative-seek semantics of the
 * write-capable + scratch-file RandomAccess family (wave 1483 siblings of the
 * wave-1482 RandomAccessReadSemanticsProbe).
 *
 * Prints, per class, the exception class + message thrown on operations after
 * close(), plus negative-seek messages where applicable.
 */
public class RandomAccessWriteScratchSemanticsProbe
{
    static String desc(Throwable t)
    {
        return t.getClass().getName() + "|" + t.getMessage();
    }

    public static void main(String[] args) throws Exception
    {
        // ---- RandomAccessReadMemoryMappedFile ----
        {
            File f = File.createTempFile("rarmm", ".bin");
            try (FileOutputStream fos = new FileOutputStream(f)) { fos.write("abc".getBytes("ISO-8859-1")); }
            RandomAccessReadMemoryMappedFile mm = new RandomAccessReadMemoryMappedFile(f);
            try { mm.seek(-1); System.out.println("mmap.seekNeg=NO_THROW"); }
            catch (Exception e) { System.out.println("mmap.seekNeg=" + desc(e)); }

            mm.seek(100);
            System.out.println("mmap.seekPastEnd.pos=" + mm.getPosition());
            System.out.println("mmap.seekPastEnd.isEOF=" + mm.isEOF());
            System.out.println("mmap.seekPastEnd.read=" + mm.read());

            mm.close();
            try { mm.read(); System.out.println("mmap.readClosed=NO_THROW"); }
            catch (Exception e) { System.out.println("mmap.readClosed=" + desc(e)); }
            try { mm.seek(0); System.out.println("mmap.seekClosed=NO_THROW"); }
            catch (Exception e) { System.out.println("mmap.seekClosed=" + desc(e)); }
            try { mm.getPosition(); System.out.println("mmap.getPosClosed=NO_THROW"); }
            catch (Exception e) { System.out.println("mmap.getPosClosed=" + desc(e)); }
            try { mm.length(); System.out.println("mmap.lengthClosed=NO_THROW"); }
            catch (Exception e) { System.out.println("mmap.lengthClosed=" + desc(e)); }
            try { mm.isEOF(); System.out.println("mmap.isEOFClosed=NO_THROW"); }
            catch (Exception e) { System.out.println("mmap.isEOFClosed=" + desc(e)); }
            f.delete();
        }

        // ---- RandomAccessReadWriteBuffer (closed -> checkClosed inherited
        //      from RandomAccessReadBuffer) ----
        {
            RandomAccessReadWriteBuffer wb = new RandomAccessReadWriteBuffer();
            wb.write("abc".getBytes("ISO-8859-1"));
            try { wb.seek(-1); System.out.println("rwbuf.seekNeg=NO_THROW"); }
            catch (Exception e) { System.out.println("rwbuf.seekNeg=" + desc(e)); }
            wb.close();
            try { wb.write(1); System.out.println("rwbuf.writeClosed=NO_THROW"); }
            catch (Exception e) { System.out.println("rwbuf.writeClosed=" + desc(e)); }
            try { wb.write("x".getBytes("ISO-8859-1")); System.out.println("rwbuf.writeBytesClosed=NO_THROW"); }
            catch (Exception e) { System.out.println("rwbuf.writeBytesClosed=" + desc(e)); }
            try { wb.clear(); System.out.println("rwbuf.clearClosed=NO_THROW"); }
            catch (Exception e) { System.out.println("rwbuf.clearClosed=" + desc(e)); }
            try { wb.read(); System.out.println("rwbuf.readClosed=NO_THROW"); }
            catch (Exception e) { System.out.println("rwbuf.readClosed=" + desc(e)); }
            try { wb.length(); System.out.println("rwbuf.lengthClosed=NO_THROW"); }
            catch (Exception e) { System.out.println("rwbuf.lengthClosed=" + desc(e)); }
        }

        // ---- ScratchFile + ScratchFileBuffer ----
        {
            ScratchFile sf = ScratchFile.getMainMemoryOnlyInstance();
            RandomAccess buf = sf.createBuffer();
            buf.write("abc".getBytes("ISO-8859-1"));
            try { buf.seek(-1); System.out.println("sbuf.seekNeg=NO_THROW"); }
            catch (Exception e) { System.out.println("sbuf.seekNeg=" + desc(e)); }

            // close just the buffer
            buf.close();
            try { buf.write(1); System.out.println("sbuf.writeBufClosed=NO_THROW"); }
            catch (Exception e) { System.out.println("sbuf.writeBufClosed=" + desc(e)); }
            try { buf.read(); System.out.println("sbuf.readBufClosed=NO_THROW"); }
            catch (Exception e) { System.out.println("sbuf.readBufClosed=" + desc(e)); }
            try { buf.seek(0); System.out.println("sbuf.seekBufClosed=NO_THROW"); }
            catch (Exception e) { System.out.println("sbuf.seekBufClosed=" + desc(e)); }
            try { buf.getPosition(); System.out.println("sbuf.getPosBufClosed=NO_THROW"); }
            catch (Exception e) { System.out.println("sbuf.getPosBufClosed=" + desc(e)); }
            try { buf.length(); System.out.println("sbuf.lengthBufClosed=NO_THROW"); }
            catch (Exception e) { System.out.println("sbuf.lengthBufClosed=" + desc(e)); }

            // now close the ScratchFile and observe createBuffer
            sf.close();
            try { sf.createBuffer(); System.out.println("sf.createBufferClosed=NO_THROW"); }
            catch (Exception e) { System.out.println("sf.createBufferClosed=" + desc(e)); }
        }
    }
}
