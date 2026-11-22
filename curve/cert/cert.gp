q = 28948022309329048851997888041834683414494990511282909948355135430626685929581;
p = 2^127 - 2437;
print("ispseudoprime(q) = ", ispseudoprime(q));
print("ispseudoprime(p) = ", ispseudoprime(p));
C = primecert(q);
print("ECPP certificate steps: ", #C);
print("primecertisvalid(C) = ", primecertisvalid(C));
Cp = primecert(p);
print("p certificate valid = ", primecertisvalid(Cp));
write("q_ecpp_certificate.txt", primecertexport(C, 1));
write("p_ecpp_certificate.txt", primecertexport(Cp, 1));
\\ Hasse-Weil interval for genus 2 and uniqueness of the multiple of q in it
lo = ceil((sqrtint(p) - 1)^4); hi = floor((sqrt(p) + 1)^4);
w = (sqrt(p)+1)^4 - (sqrt(p)-1)^4;
print("interval width bits = ", log(w)/log(2), "   q bits = ", log(q)/log(2));
print("q in [ (sqrt p - 1)^4, (sqrt p + 1)^4 ] : ", (sqrt(p)-1)^4 <= q && q <= (sqrt(p)+1)^4);
print("2q > (sqrt p + 1)^4 : ", 2*q > (sqrt(p)+1)^4);
