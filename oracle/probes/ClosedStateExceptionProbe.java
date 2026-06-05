import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.fdf.FDFDocument;

import java.io.ByteArrayOutputStream;
import java.io.OutputStream;

/**
 * Differential probe for the closed-state exception family.
 *
 * Prints, per operation, the exception class + message thrown after the
 * owning object has been closed:
 *   - COSStream:  createOutputStream / createRawOutputStream after the
 *                 enclosing scratch (PDDocument) is closed -> checkClosed()
 *   - PDDocument: save() after close() -> IOException("Cannot save a
 *                 document which has been closed")
 *
 * COSStream's checkClosed() throws
 *   IOException("COSStream has been closed and cannot be read. " +
 *               "Perhaps its enclosing PDDocument has been closed?")
 */
public class ClosedStateExceptionProbe
{
    static String desc(Throwable t)
    {
        return t.getClass().getName() + "|" + t.getMessage();
    }

    public static void main(String[] args) throws Exception
    {
        // ---- COSStream after enclosing document closed ----
        {
            PDDocument doc = new PDDocument();
            COSStream stream = doc.getDocument().createCOSStream();
            // write some bytes so the stream has a body, fully closing the writer
            OutputStream os = stream.createOutputStream();
            os.write("body".getBytes("ISO-8859-1"));
            os.close();
            doc.close(); // closes the scratch backing store

            try { stream.createRawInputStream(); System.out.println("cosstream.createRawInputStream=NO_THROW"); }
            catch (Throwable e) { System.out.println("cosstream.createRawInputStream=" + desc(e)); }
            try { stream.createOutputStream(); System.out.println("cosstream.createOutputStream=NO_THROW"); }
            catch (Throwable e) { System.out.println("cosstream.createOutputStream=" + desc(e)); }
            try { stream.createRawOutputStream(); System.out.println("cosstream.createRawOutputStream=NO_THROW"); }
            catch (Throwable e) { System.out.println("cosstream.createRawOutputStream=" + desc(e)); }
        }

        // ---- PDDocument.save() after close() ----
        {
            PDDocument doc = new PDDocument();
            doc.addPage(new PDPage());
            doc.close();
            ByteArrayOutputStream sink = new ByteArrayOutputStream();
            try { doc.save(sink); System.out.println("pddocument.save=NO_THROW"); }
            catch (Throwable e) { System.out.println("pddocument.save=" + desc(e)); }
        }

        // ---- FDFDocument: upstream has no closed-state guard on save ----
        {
            FDFDocument fdf = new FDFDocument();
            fdf.close();
            ByteArrayOutputStream sink = new ByteArrayOutputStream();
            try { fdf.save(sink); System.out.println("fdfdocument.save=NO_THROW"); }
            catch (Throwable e) { System.out.println("fdfdocument.save=" + desc(e)); }
        }
    }
}
