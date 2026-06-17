import java.io.File;
import java.io.InputStream;
import java.io.OutputStream;
import java.io.PrintStream;
import java.math.BigInteger;
import java.nio.file.Files;
import java.security.KeyPair;
import java.security.KeyPairGenerator;
import java.security.PrivateKey;
import java.security.Security;
import java.security.cert.X509Certificate;
import java.util.Calendar;
import java.util.Date;
import java.util.List;

import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.interactive.digitalsignature.PDSignature;
import org.apache.pdfbox.pdmodel.interactive.digitalsignature.SignatureInterface;

import org.bouncycastle.asn1.x500.X500Name;
import org.bouncycastle.cert.X509CertificateHolder;
import org.bouncycastle.cert.jcajce.JcaCertStore;
import org.bouncycastle.cert.jcajce.JcaX509CertificateConverter;
import org.bouncycastle.cert.jcajce.JcaX509v3CertificateBuilder;
import org.bouncycastle.cms.CMSSignedData;
import org.bouncycastle.cms.CMSSignedDataGenerator;
import org.bouncycastle.cms.CMSTypedData;
import org.bouncycastle.cms.CMSProcessableByteArray;
import org.bouncycastle.cms.jcajce.JcaSignerInfoGeneratorBuilder;
import org.bouncycastle.jce.provider.BouncyCastleProvider;
import org.bouncycastle.operator.ContentSigner;
import org.bouncycastle.operator.jcajce.JcaContentSignerBuilder;
import org.bouncycastle.operator.jcajce.JcaDigestCalculatorProviderBuilder;

/**
 * Live oracle probe: sign a PDF with Apache PDFBox and report whether
 * PDFBox's own COSWriter places the /Contents `<`/`>` delimiters INSIDE or
 * OUTSIDE the /ByteRange chunks.
 *
 * This is the ground-truth check for the writer convention. PDFBox's
 * COSWriter computes:
 *   beforeLength = signatureOffset            (= position of `<`)
 *   afterOffset  = signatureOffset + signatureLength  (= position after `>`)
 * so the EXPECTED convention is brackets-EXCLUDED:
 *   fileBytes[a+b]   == '<'   (the `<` is the FIRST excluded byte)
 *   fileBytes[c-1]   == '>'   (the `>` is the LAST excluded byte)
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> SignByteRangeConventionProbe in.pdf
 * Output (stdout, one key=value per line):
 *   byterange=a,b,c,d
 *   fileLength=<raw signed file size>
 *   byteAt[a+b]=<char>          (expected '<' under brackets-EXCLUDED)
 *   byteAt[a+b-1]=<char>        (expected '<' under brackets-INCLUDED)
 *   byteAt[c]=<char>            (expected '>' under brackets-INCLUDED)
 *   byteAt[c-1]=<char>          (expected '>' under brackets-EXCLUDED)
 *   convention=<excluded|included|other>
 */
public final class SignByteRangeConventionProbe {

    private static final String SUBJECT_DN =
            "CN=oracle-byterange-convention,O=pypdfbox-oracle,C=US";

    public static void main(String[] args) throws Exception {
        Security.addProvider(new BouncyCastleProvider());
        PrintStream out = new PrintStream(System.out, true, "UTF-8");

        File in = new File(args[0]);
        File outFile = File.createTempFile("brconv", ".pdf");
        outFile.deleteOnExit();

        KeyPairGenerator kpg = KeyPairGenerator.getInstance("RSA");
        kpg.initialize(2048);
        KeyPair kp = kpg.generateKeyPair();
        final PrivateKey privateKey = kp.getPrivate();

        BigInteger serial = BigInteger.valueOf(System.currentTimeMillis());
        Calendar cal = Calendar.getInstance();
        Date notBefore = new Date(cal.getTimeInMillis() - 60_000L);
        cal.add(Calendar.DAY_OF_YEAR, 1);
        Date notAfter = cal.getTime();
        X500Name dn = new X500Name(SUBJECT_DN);

        JcaX509v3CertificateBuilder certBuilder = new JcaX509v3CertificateBuilder(
                dn, serial, notBefore, notAfter, dn, kp.getPublic());
        ContentSigner certSigner = new JcaContentSignerBuilder("SHA256withRSA")
                .setProvider(BouncyCastleProvider.PROVIDER_NAME)
                .build(privateKey);
        X509CertificateHolder holder = certBuilder.build(certSigner);
        final X509Certificate certificate = new JcaX509CertificateConverter()
                .setProvider(BouncyCastleProvider.PROVIDER_NAME)
                .getCertificate(holder);

        SignatureInterface signer = new SignatureInterface() {
            @Override
            public byte[] sign(InputStream content) throws java.io.IOException {
                try {
                    byte[] data = content.readAllBytes();
                    CMSTypedData typed = new CMSProcessableByteArray(data);
                    CMSSignedDataGenerator gen = new CMSSignedDataGenerator();
                    ContentSigner sha256Signer =
                            new JcaContentSignerBuilder("SHA256withRSA")
                                    .setProvider(BouncyCastleProvider.PROVIDER_NAME)
                                    .build(privateKey);
                    gen.addSignerInfoGenerator(
                            new JcaSignerInfoGeneratorBuilder(
                                    new JcaDigestCalculatorProviderBuilder()
                                            .setProvider(BouncyCastleProvider.PROVIDER_NAME)
                                            .build())
                                    .build(sha256Signer, certificate));
                    gen.addCertificates(new JcaCertStore(
                            java.util.Collections.singletonList(certificate)));
                    CMSSignedData signed = gen.generate(typed, false);
                    return signed.getEncoded();
                } catch (Exception e) {
                    throw new java.io.IOException(e);
                }
            }
        };

        try (PDDocument doc = Loader.loadPDF(in)) {
            PDSignature signature = new PDSignature();
            signature.setFilter(PDSignature.FILTER_ADOBE_PPKLITE);
            signature.setSubFilter(PDSignature.SUBFILTER_ADBE_PKCS7_DETACHED);
            signature.setName("Oracle ByteRange Convention Probe");
            signature.setSignDate(Calendar.getInstance());
            doc.addSignature(signature, signer);
            try (OutputStream os = Files.newOutputStream(outFile.toPath(),
                    java.nio.file.StandardOpenOption.CREATE,
                    java.nio.file.StandardOpenOption.TRUNCATE_EXISTING,
                    java.nio.file.StandardOpenOption.WRITE)) {
                doc.saveIncremental(os);
            }
        }

        byte[] fileBytes = Files.readAllBytes(outFile.toPath());
        try (PDDocument doc = Loader.loadPDF(outFile)) {
            List<PDSignature> sigs = doc.getSignatureDictionaries();
            PDSignature sig = sigs.get(0);
            int[] br = sig.getByteRange();
            int a = br[0], b = br[1], c = br[2], d = br[3];
            out.println("byterange=" + a + "," + b + "," + c + "," + d);
            out.println("fileLength=" + fileBytes.length);
            out.println("byteAt[a+b]=" + safeChar(fileBytes, a + b));
            out.println("byteAt[a+b-1]=" + safeChar(fileBytes, a + b - 1));
            out.println("byteAt[c]=" + safeChar(fileBytes, c));
            out.println("byteAt[c-1]=" + safeChar(fileBytes, c - 1));

            boolean excluded = isChar(fileBytes, a + b, '<')
                    && isChar(fileBytes, c - 1, '>');
            boolean included = isChar(fileBytes, a + b - 1, '<')
                    && isChar(fileBytes, c, '>');
            String convention = excluded ? "excluded"
                    : (included ? "included" : "other");
            out.println("convention=" + convention);

            // Also report what getContents(byte[]) extracts vs the embedded
            // COSString /Contents — they must agree under the right convention.
            byte[] viaByteRange = sig.getContents(fileBytes);
            byte[] viaCosString = sig.getContents();
            out.println("getContentsByteRangeLen=" + viaByteRange.length);
            out.println("getContentsCosStringLen=" + viaCosString.length);
            out.println("getContentsAgree="
                    + java.util.Arrays.equals(viaByteRange, viaCosString));
        }
    }

    private static String safeChar(byte[] buf, int idx) {
        if (idx < 0 || idx >= buf.length) {
            return "<oob>";
        }
        char ch = (char) (buf[idx] & 0xFF);
        return String.valueOf(ch);
    }

    private static boolean isChar(byte[] buf, int idx, char want) {
        return idx >= 0 && idx < buf.length && (char) (buf[idx] & 0xFF) == want;
    }
}
