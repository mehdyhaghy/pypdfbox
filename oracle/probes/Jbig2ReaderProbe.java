import java.awt.Dimension;
import java.awt.Rectangle;
import java.awt.image.Raster;
import java.io.ByteArrayInputStream;

import javax.imageio.stream.ImageInputStream;
import javax.imageio.stream.MemoryCacheImageInputStream;

import org.apache.pdfbox.jbig2.JBIG2ImageReader;
import org.apache.pdfbox.jbig2.JBIG2ImageReaderSpi;
import org.apache.pdfbox.jbig2.JBIG2ReadParam;

/**
 * Live oracle probe for the upstream {@code JBIG2ImageReader} public API.
 *
 * Drives {@code JBIG2ImageReader.readRaster(0, JBIG2ReadParam)} for a chosen
 * page and read-param (source region + subsampling) and dumps the resulting
 * {@link Raster}'s packed bytes. A parity test asserts pypdfbox's
 * {@code JBIG2ImageReader.read_raster(...)} produces the identical raster bytes,
 * plus matching width/height/numImages.
 *
 * The reader builds a single-band TYPE_BYTE raster; for the unscaled bilevel
 * case the underlying DataBuffer is the packed, polarity-inverted scanline
 * buffer (sample 0 = black). We dump that buffer directly to mirror pypdfbox's
 * {@code Bitmaps.as_raster} return value byte-for-byte.
 *
 * Usage:
 *   java ... Jbig2ReaderProbe &lt;hexbytes&gt; &lt;pageIndex&gt; &lt;rx&gt; &lt;ry&gt; &lt;rw&gt; &lt;rh&gt; &lt;xsub&gt; &lt;ysub&gt; &lt;xoff&gt; &lt;yoff&gt; [&lt;rrw&gt; &lt;rrh&gt;]
 *
 *   pageIndex   0-based page index.
 *   rx ry rw rh source region; pass rw or rh &lt;= 0 to use no source region.
 *   xsub ysub   subsampling factors (&gt;= 1).
 *   xoff yoff   subsampling offsets.
 *   rrw rrh     optional source render size; pass rrw or rrh &lt;= 0 (or omit) to
 *               use no render size. When set, the reader resamples and the
 *               dumped raster is single-band 8-bit grayscale (1 byte/pixel).
 *
 * Output (UTF-8, single LF-terminated line):
 *   "&lt;numImages&gt; &lt;width&gt; &lt;height&gt; &lt;hexBytes&gt;"
 *   where width/height are the reader's getWidth/getHeight for the page and
 *   hexBytes is the packed raster DataBuffer content.
 */
public final class Jbig2ReaderProbe
{
    public static void main(String[] args) throws Exception
    {
        if (args.length < 10)
        {
            System.err.println("usage: Jbig2ReaderProbe <hex> <pageIndex> <rx> <ry> <rw> <rh>"
                    + " <xsub> <ysub> <xoff> <yoff>");
            System.exit(2);
        }

        byte[] data = hex(args[0]);
        int pageIndex = Integer.parseInt(args[1]);
        int rx = Integer.parseInt(args[2]);
        int ry = Integer.parseInt(args[3]);
        int rw = Integer.parseInt(args[4]);
        int rh = Integer.parseInt(args[5]);
        int xsub = Integer.parseInt(args[6]);
        int ysub = Integer.parseInt(args[7]);
        int xoff = Integer.parseInt(args[8]);
        int yoff = Integer.parseInt(args[9]);
        int rrw = args.length > 10 ? Integer.parseInt(args[10]) : 0;
        int rrh = args.length > 11 ? Integer.parseInt(args[11]) : 0;

        ImageInputStream iis =
                new MemoryCacheImageInputStream(new ByteArrayInputStream(data));

        JBIG2ImageReader reader = new JBIG2ImageReader(new JBIG2ImageReaderSpi());
        reader.setInput(iis);

        int numImages = reader.getNumImages(true);
        int width = reader.getWidth(pageIndex);
        int height = reader.getHeight(pageIndex);

        Rectangle region = (rw > 0 && rh > 0) ? new Rectangle(rx, ry, rw, rh) : null;
        Dimension renderSize = (rrw > 0 && rrh > 0) ? new Dimension(rrw, rrh) : null;
        JBIG2ReadParam param =
                new JBIG2ReadParam(xsub, ysub, xoff, yoff, region, renderSize);

        Raster raster = reader.readRaster(pageIndex, param);
        java.awt.image.DataBuffer db = raster.getDataBuffer();
        java.awt.image.DataBufferByte dbb = (java.awt.image.DataBufferByte) db;
        byte[] bytes = dbb.getData();

        StringBuilder sb = new StringBuilder();
        sb.append(numImages).append(' ')
          .append(width).append(' ')
          .append(height).append(' ');
        for (byte b : bytes)
        {
            sb.append(String.format("%02x", b & 0xff));
        }
        sb.append('\n');

        System.out.print(sb);
        System.out.flush();
    }

    private static byte[] hex(String s)
    {
        int n = s.length() / 2;
        byte[] out = new byte[n];
        for (int i = 0; i < n; i++)
        {
            out[i] = (byte) Integer.parseInt(s.substring(2 * i, 2 * i + 2), 16);
        }
        return out;
    }
}
