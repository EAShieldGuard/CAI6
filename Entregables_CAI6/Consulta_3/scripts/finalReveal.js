const { ethers } = require("hardhat");

const AUCTION_ADDRESS = process.env.AUCTION_ADDRESS;

const BIDS = [
  {
    name: "Proveedor A",
    privateKey: process.env.PROVIDER_A_PRIVATE_KEY,
    amount: ethers.parseEther("0.001"),
    secret: "cai6FinalA",
  },
  {
    name: "Proveedor B",
    privateKey: process.env.PROVIDER_B_PRIVATE_KEY,
    amount: ethers.parseEther("0.0008"),
    secret: "cai6FinalB",
  },
  {
    name: "Proveedor C",
    privateKey: process.env.PROVIDER_C_PRIVATE_KEY,
    amount: ethers.parseEther("0.0012"),
    secret: "cai6FinalC",
  },
];

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

  const auction = await ethers.getContractAt(
    "HealthProcurementAuction",
    AUCTION_ADDRESS
  );

  const biddingDeadline = await auction.biddingDeadline();
  const revealDeadline = await auction.revealDeadline();

  let block = await ethers.provider.getBlock("latest");
  let now = BigInt(block.timestamp);

  console.log("Auction:", AUCTION_ADDRESS);
  console.log("Ahora:", now.toString(), dateFromUnix(now));
  console.log("biddingDeadline:", biddingDeadline.toString(), dateFromUnix(biddingDeadline));
  console.log("revealDeadline:", revealDeadline.toString(), dateFromUnix(revealDeadline));

  if (now <= biddingDeadline) {
    const waitSeconds = Number(biddingDeadline - now + 3n);
    console.log(`Aún no está abierta reveal. Esperando ${waitSeconds} segundos...`);
    await sleep(waitSeconds * 1000);
  }

  block = await ethers.provider.getBlock("latest");
  now = BigInt(block.timestamp);

  if (now >= revealDeadline) {
    throw new Error("La fase reveal ya terminó. Despliega otra Auction.");
  }

  console.log("revealOpen:", await auction.revealOpen());
  console.log("\n=== REVEAL BIDS ===");

  for (const bid of BIDS) {
    const wallet = new ethers.Wallet(bid.privateKey, ethers.provider);

    const bBefore = await auction.bidders(wallet.address);

    console.log(`\n${bid.name}`);
    console.log("Wallet:", wallet.address);
    console.log("Amount wei:", bid.amount.toString());
    console.log("Amount ETH:", ethers.formatEther(bid.amount));
    console.log("Secret:", bid.secret);
    console.log("Committed:", bBefore.committed);
    console.log("Has revealed:", bBefore.hasRevealed);

    if (!bBefore.committed) {
      throw new Error(`${bid.name}: esta wallet no hizo commit`);
    }

    if (bBefore.hasRevealed) {
      console.log(`${bid.name}: ya estaba revelado, se salta`);
      continue;
    }

    const computedHash = ethers.solidityPackedKeccak256(
      ["uint256", "string"],
      [bid.amount, bid.secret]
    );

    console.log("Computed hash:", computedHash);
    console.log("On-chain hash:", bBefore.commitHash);

    if (computedHash.toLowerCase() !== bBefore.commitHash.toLowerCase()) {
      throw new Error(`${bid.name}: commitHash no coincide`);
    }

    const tx = await auction.connect(wallet).revealBid(
      bid.amount,
      bid.secret
    );

    console.log("revealBid tx:", tx.hash);
    await tx.wait();
    console.log("revealBid confirmado");

    const bAfter = await auction.bidders(wallet.address);
    console.log("revealedBid:", bAfter.revealedBid.toString());
    console.log("hasRevealed:", bAfter.hasRevealed);
  }

  const totalRevealed = await auction.totalRevealed();
  console.log("\nTotal revealed:", totalRevealed.toString());
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});