import java.io.ByteArrayInputStream;
import javax.imageio.stream.ImageInputStream;
import javax.imageio.stream.MemoryCacheImageInputStream;
import org.apache.pdfbox.jbig2.decoder.arithmetic.ArithmeticDecoder;
import org.apache.pdfbox.jbig2.decoder.arithmetic.CX;

/**
 * Live oracle probe for the JBIG2 MQ arithmetic decoder.
 *
 * Drives the upstream Apache PDFBox {@link ArithmeticDecoder} (+ {@link CX})
 * on a fixed input byte array and emits the decoded bit sequence so a parity
 * test can assert pypdfbox's ArithmeticDecoder produces the identical bits.
 *
 * Usage:
 *   java ... ArithDecodeProbe <hexbytes> <nbits> [ctxsize] [index] [cycle]
 *
 *   hexbytes  the coded input as a hex string, e.g. "84c73b" (no 0x, even len)
 *   nbits     number of bits to decode
 *   ctxsize   context-array size (default 512)
 *   index     base context index used for every decode (default 0)
 *   cycle     if "cycle", the context index walks 0..ctxsize-1 round-robin so
 *             multiple distinct probability states are exercised; otherwise the
 *             index stays fixed at <index> (single-state evolution).
 *
 * The {@code MemoryCacheImageInputStream} wrapping a {@code ByteArrayInputStream}
 * provides exactly the {@code ImageInputStream} surface the decoder uses
 * (read / getStreamPosition / seek), mirroring pypdfbox's io reader contract.
 *
 * Output (UTF-8, single LF-terminated line): the decoded bits with no
 * separator, e.g. "0110100...".
 */
public final class ArithDecodeProbe
{
    public static void main(String[] args) throws Exception
    {
        if (args.length < 2)
        {
            System.err.println(
                "usage: ArithDecodeProbe <hexbytes> <nbits> [ctxsize] [index] [cycle]");
            System.exit(2);
        }

        byte[] data = hex(args[0]);
        int nbits = Integer.parseInt(args[1]);
        int ctxSize = args.length >= 3 ? Integer.parseInt(args[2]) : 512;
        int index = args.length >= 4 ? Integer.parseInt(args[3]) : 0;
        boolean cycle = args.length >= 5 && "cycle".equals(args[4]);

        ImageInputStream iis =
            new MemoryCacheImageInputStream(new ByteArrayInputStream(data));

        ArithmeticDecoder decoder = new ArithmeticDecoder(iis);
        CX cx = new CX(ctxSize, index);

        StringBuilder sb = new StringBuilder(nbits);
        for (int i = 0; i < nbits; i++)
        {
            if (cycle)
            {
                cx.setIndex(i % ctxSize);
            }
            else
            {
                cx.setIndex(index);
            }
            int bit = decoder.decode(cx);
            sb.append(bit);
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
