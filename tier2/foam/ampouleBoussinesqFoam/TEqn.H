{
    alphat = turbulence->nut()/Prt;
    alphat.correctBoundaryConditions();

    volScalarField alphaEff("alphaEff", turbulence->nu()/Pr + alphat);

    fvScalarMatrix TEqn
    (
        fvm::ddt(T)
      + fvm::div(phi, T)
      - fvm::laplacian(alphaEff, T)
     ==
        radiation->ST(rhoCpRef, T)
      + fvOptions(T)
    );

    TEqn.relax();

    fvOptions.constrain(TEqn);

    TEqn.solve();

    radiation->correct();

    fvOptions.correct(T);

    fvScalarMatrix YEqn(fvm::ddt(Y) + fvm::div(phi, Y) - fvm::laplacian(Dy, Y));
    YEqn.solve();
    rhok = 1.0 - beta*(T - TRef) - betaS*(Y - Yref);
}
