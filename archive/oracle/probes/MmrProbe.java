import java.io.ByteArrayInputStream;
import javax.imageio.stream.ImageInputStream;
import javax.imageio.stream.MemoryCacheImageInputStream;
import org.apache.pdfbox.jbig2.Bitmap;
import org.apache.pdfbox.jbig2.decoder.mmr.MMRDecompressor;

/**
 * Live oracle probe for the JBIG2 MMR (ITU-T T.6 / CCITT Group-4) decoder.
 *
 * Drives the upstream Apache PDFBox {@link MMRDecompressor} on a fixed
 * CCITT-G4-encoded byte array and emits the decoded bitmap (dimensions plus the
 * packed bytes as hex) so a parity test can assert pypdfbox's MMRDecompressor
 * produces the IDENTICAL bitmap.
 *
 * Usage:
 *   java ... MmrProbe <hexbytes> <width> <height>
 *
 *   hexbytes  the CCITT-G4 coded input as a hex string (no 0x, even length)
 *   width     bitmap width in pixels
 *   height    bitmap height in pixels
 *
 * The {@code MemoryCacheImageInputStream} wrapping a {@code ByteArrayInputStream}
 * provides exactly the {@code ImageInputStream} surface the decompressor uses
 * (length / seek / read), mirroring pypdfbox's io reader contract.
 *
 * Output (UTF-8, single LF-terminated line):
 *   "<width> <height> <rowStride> <hexOfPackedBytes>"
 */
public final class MmrProbe
{
    public static void main(String[] args) throws Exception
    {
        if (args.length < 3)
        {
            System.err.println("usage: MmrProbe <hexbytes> <width> <height>");
            System.exit(2);
        }

        byte[] data = hex(args[0]);
        int width = Integer.parseInt(args[1]);
        int height = Integer.parseInt(args[2]);

        ImageInputStream iis =
            new MemoryCacheImageInputStream(new ByteArrayInputStream(data));

        MMRDecompressor decompressor = new MMRDecompressor(width, height, iis);
        Bitmap bitmap = decompressor.uncompress();

        byte[] bytes = bitmap.getByteArray();

        StringBuilder sb = new StringBuilder();
        sb.append(bitmap.getWidth());
        sb.append(' ');
        sb.append(bitmap.getHeight());
        sb.append(' ');
        sb.append(bitmap.getRowStride());
        sb.append(' ');
        for (byte b : bytes)
        {
            sb.append(String.format("%02x", b & 0xff));
        }

        System.out.print(sb.toString());
        System.out.print('\n');
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
