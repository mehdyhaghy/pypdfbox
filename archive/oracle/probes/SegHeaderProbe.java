import java.io.ByteArrayInputStream;
import java.lang.reflect.Constructor;

import javax.imageio.stream.MemoryCacheImageInputStream;

import org.apache.pdfbox.jbig2.SegmentHeader;
import org.apache.pdfbox.jbig2.io.SubInputStream;

/**
 * Live oracle probe for the JBIG2 segment-header parser.
 *
 * Drives the upstream Apache PDFBox {@link SegmentHeader} on a fixed byte array
 * containing one or more concatenated segment headers, and dumps the parsed
 * fields of each header so a parity test can assert pypdfbox's SegmentHeader
 * parses the identical values.
 *
 * The {@link SegmentHeader} constructor is package-private and takes a
 * JBIG2Document used only to resolve referred-to segments (when the referred-to
 * count is greater than zero). The probe crafts headers with zero referred-to
 * segments, so the document is never dereferenced; a {@code null} document is
 * passed via reflection (the only way to reach the package-private constructor
 * from the default package). organisationType is always SEQUENTIAL (1) so the
 * data start offset is recorded.
 *
 * Usage:
 *   java ... SegHeaderProbe &lt;hexbytes&gt; &lt;count&gt;
 *
 *   hexbytes  the segment-header stream as a hex string (no 0x, even length)
 *   count     number of consecutive headers to parse
 *
 * Output (UTF-8): one line per header, fields separated by a single space:
 *   segmentNr segmentType pageAssociation retainFlag headerLength dataLength dataStartOffset
 */
public final class SegHeaderProbe
{
    private static final int SEQUENTIAL = 1;

    public static void main(String[] args) throws Exception
    {
        if (args.length < 2)
        {
            System.err.println("usage: SegHeaderProbe <hexbytes> <count>");
            System.exit(2);
        }

        byte[] data = hexToBytes(args[0]);
        int count = Integer.parseInt(args[1]);

        MemoryCacheImageInputStream iis =
                new MemoryCacheImageInputStream(new ByteArrayInputStream(data));
        SubInputStream sis = new SubInputStream(iis, 0, data.length);

        Constructor<SegmentHeader> ctor = SegmentHeader.class.getDeclaredConstructor(
                Class.forName("org.apache.pdfbox.jbig2.JBIG2Document"),
                SubInputStream.class, long.class, int.class);
        ctor.setAccessible(true);

        StringBuilder out = new StringBuilder();
        long offset = 0;
        for (int i = 0; i < count; i++)
        {
            SegmentHeader header = ctor.newInstance(null, sis, offset, SEQUENTIAL);
            out.append(header.getSegmentNr()).append(' ')
               .append(header.getSegmentType()).append(' ')
               .append(header.getPageAssociation()).append(' ')
               .append(header.getRetainFlag()).append(' ')
               .append(header.getSegmentHeaderLength()).append(' ')
               .append(header.getSegmentDataLength()).append(' ')
               .append(header.getSegmentDataStartOffset()).append('\n');
            // Advance past this header AND its data part to the next header.
            offset = header.getSegmentDataStartOffset() + header.getSegmentDataLength();
        }

        System.out.print(out);
    }

    private static byte[] hexToBytes(String hex)
    {
        int len = hex.length();
        byte[] data = new byte[len / 2];
        for (int i = 0; i < len; i += 2)
        {
            data[i / 2] = (byte) ((Character.digit(hex.charAt(i), 16) << 4)
                    + Character.digit(hex.charAt(i + 1), 16));
        }
        return data;
    }
}
