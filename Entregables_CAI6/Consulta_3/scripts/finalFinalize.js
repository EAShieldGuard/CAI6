const { ethers } = require("hardhat");

const AUCTION_ADDRESS = process.env.AUCTION_ADDRESS;

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function dateFromUnix(ts) {
  return new Date(Number(ts) * 1000).toISOString();
}

async function main() {
  if (!AUCTION_ADDRESS) {
    throw new Error("Falta AUCTION_ADDRESS en .env");
  }

  const [deployer] = await ethers.getSigners();

  const auction = await ethers.getContractAt(
    "HealthProcurementAuction",
    AUCTION_ADDRESS
  );

  const revealDeadline = await auction.revealDeadline();

  let block = await ethers.provider.getBlock("latest");
  let now = BigInt(block.timestamp);

  console.log("Auction:", AUCTION_ADDRESS);
  console.log("ServicioSalud:", deployer.address);
  console.log("Ahora:", now.toString(), dateFromUnix(now));
  console.log("revealDeadline:", revealDeadline.toString(), dateFromUnix(revealDeadline));

  if (now <= revealDeadline) {
    const waitSeconds = Number(revealDeadline - now + 3n);
    console.log(`Esperando ${waitSeconds} segundos hasta poder finalizar...`);
    await sleep(waitSeconds * 1000);
  }

  const alreadyFinalized = await auction.isFinalized();

  if (!alreadyFinalized) {
    const tx = await auction.connect(deployer).finalizeAuction();
    console.log("finalizeAuction tx:", tx.hash);
    await tx.wait();
    console.log("finalizeAuction confirmado");
  } else {
    console.log("La subasta ya estaba finalizada");
  }

  const winner = await auction.winner();
  const winningBid = await auction.winningBid();
  const priceToPay = await auction.priceToPay();
  const isFinalized = await auction.isFinalized();

  console.log("\n=== RESULTADO ===");
  console.log("isFinalized:", isFinalized);
  console.log("winner:", winner);
  console.log("winningBid wei:", winningBid.toString());
  console.log("winningBid ETH:", ethers.formatEther(winningBid));
  console.log("priceToPay wei:", priceToPay.toString());
  console.log("priceToPay ETH:", ethers.formatEther(priceToPay));
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});