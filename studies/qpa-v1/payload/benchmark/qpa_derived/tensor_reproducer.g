# Minimal released-QPA reproduction: k tensor_k k, including its bilinear map.
# Run with GAP --bare -A -q --nointeract --quitonbreak.
if LoadPackage("qpa")<>true then Error("QPA unavailable");fi;
AlwaysPrintTracebackOnError:=true;;
Q:=Quiver(1,[]);; A:=PathAlgebra(Rationals,Q);;
M:=RightModuleOverPathAlgebra(A,[1],[]);;
N:=RightModuleOverPathAlgebra(OppositeAlgebra(A),[1],[]);;
T:=TensorProductOfModules(M,N);;
Print("Tensor dimension: ",Dimension(T[1])," (expected 1)\n");
Print("Evaluating 1 tensor 1 through QPA's returned function:\n");
T[2](BasisVectors(Basis(M))[1],BasisVectors(Basis(N))[1]);
QUIT;
