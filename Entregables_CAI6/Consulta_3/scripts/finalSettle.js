const { ethers } = require("hardhat");

const AUCTION_ADDRESS = process.env.AUCTION_ADDRESS;

const PROVIDERS = [
  {
    name: "Proveedor A",
    privateKey: process.env.PROVIDER_A_PRIVATE_KEY,
  },
  {
    name: "Proveedor B",
    privateKey: process.env.PROVIDER_B_PRIVATE_KEY,
  },
  {
    name: "Proveedor C",
    privateKey: process.env.PROVIDER_C_PRIVATE_KEY,
  },
];

async function main() {
  if (!AUCTION_ADDRESS) {
    throw new Error("Falta AUCTION_ADDRESS en .env");
  }

  const [deployer] = await ethers.getSigners();

  const auction = await ethers.getContractAt(
    "HealthProcurementAuction",
    AUCTION_ADDRESS
  );

  const isFinalized = await auction.isFinalized();

  if (!isFinalized) {
    throw new Error("La subasta todavía no está finalizada");
  }

  const winner = await auction.winner();
  const priceToPay = await auction.priceToPay();

  console.log("Auction:", AUCTION_ADDRESS);
  console.log("ServicioSalud:", deployer.address);
  console.log("winner:", winner);
  console.log("priceToPay wei:", priceToPay.toString());
  console.log("priceToPay ETH:", ethers.formatEther(priceToPay));

  const deliveryConfirmed = await auction.deliveryConfirmed();
  const winnerPenalized = await auction.winnerPenalized();

  if (!deliveryConfirmed && !winnerPenalized) {
    console.log("\nConfirmando entrega y pagando al ganador...");

    const tx = await auction.connect(deployer).confirmDeliveryAndPay({
      value: priceToPay,
    });

    console.log("confirmDeliveryAndPay tx:", tx.hash);
    await tx.wait();
    console.log("confirmDeliveryAndPay confirmado");
  } else {
    console.log("Entrega ya confirmada o ganador penalizado");
  }

  console.log("\nRetirando depósitos de proveedores no ganadores...");

  for (const provider of PROVIDERS) {
    const wallet = new ethers.Wallet(provider.privateKey, ethers.provider);
    const address = wallet.address;

    const b = await auction.bidders(address);
    const isWinner = address.toLowerCase() === winner.toLowerCase();

    console.log(`\n${provider.name}`);
    console.log("Wallet:", address);
    console.log("Deposit:", ethers.formatEther(b.deposit), "ETH");
    console.log("depositWithdrawn:", b.depositWithdrawn);
    console.log("isWinner:", isWinner);

    if (!isWinner && b.deposit > 0n && !b.depositWithdrawn) {
      const tx = await auction.connect(wallet).withdrawDeposit();
      console.log("withdrawDeposit tx:", tx.hash);
      await tx.wait();
      console.log("withdrawDeposit confirmado");
    } else {
      console.log("No hay depósito recuperable para esta cuenta");
    }
  }

  console.log("\nEstado final:");
  console.log("deliveryConfirmed:", await auction.deliveryConfirmed());
  console.log("winnerPenalized:", await auction.winnerPenalized());
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});