import org.apache.pdfbox.pdmodel.interactive.digitalsignature.COSFilterInputStream;

/**
 * Differential probe for COSFilterInputStream read-after-close behaviour.
 *
 * COSFilterInputStream extends java.io.FilterInputStream. Its close() is
 * inherited (FilterInputStream.close() -> in.close()). When constructed from a
 * byte[] the backing stream is a ByteArrayInputStream whose close() is a no-op
 * and whose read() keeps working after close(). So a read after close() does
 * NOT throw on the byte[] overload — it returns -1 once the configured ranges
 * are exhausted, or the next in-range byte otherwise.
 *
 * Prints, per operation, NO_THROW=<intResult> or the exception class+message.
 */
public class COSFilterInputStreamClosedProbe
{
    static String desc(Throwable t)
    {
        return t.getClass().getName() + "|" + t.getMessage();
    }

    public static void main(String[] args) throws Exception
    {
        byte[] payload = "ABCDEFGHIJKLMNOP".getBytes("ISO-8859-1");
        // ByteRange [0,4, 8,4] -> covers "ABCD" + "IJKL"
        int[] byteRange = new int[] { 0, 4, 8, 4 };

        // ---- read() single-byte after close, fresh stream ----
        {
            COSFilterInputStream s = new COSFilterInputStream(payload, byteRange);
            s.close();
            try { int r = s.read(); System.out.println("read_after_close_fresh=NO_THROW=" + r); }
            catch (Throwable e) { System.out.println("read_after_close_fresh=" + desc(e)); }
        }

        // ---- read(byte[],off,len) after close, fresh stream ----
        {
            COSFilterInputStream s = new COSFilterInputStream(payload, byteRange);
            s.close();
            byte[] buf = new byte[4];
            try { int r = s.read(buf, 0, 4); System.out.println("read_buf_after_close_fresh=NO_THROW=" + r); }
            catch (Throwable e) { System.out.println("read_buf_after_close_fresh=" + desc(e)); }
        }

        // ---- read after fully consuming then close ----
        {
            COSFilterInputStream s = new COSFilterInputStream(payload, byteRange);
            byte[] all = s.toByteArray();
            s.close();
            try { int r = s.read(); System.out.println("read_after_consume_close=NO_THROW=" + r + ";consumed=" + new String(all, "ISO-8859-1")); }
            catch (Throwable e) { System.out.println("read_after_consume_close=" + desc(e)); }
        }
    }
}
